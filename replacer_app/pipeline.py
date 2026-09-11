"""Isolated builds: the saved pose file is the only source of geometry."""
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path
from fluffy_package import package_name, package_directory

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def run_blender_stage(blender,script,request,work,job,stage):
    log = work/(stage+'.log')
    with log.open('w',encoding='utf-8') as out:
        process = subprocess.Popen([str(blender),'-b','--python-exit-code','1','--python',str(script),
                                    '--',str(request)],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT)
        started = time.monotonic()
        while process.poll() is None:
            if time.monotonic()-started > 1800:
                process.kill();process.wait()
                raise TimeoutError(f'构建超时，现场保留：{work}')
            job['stdout'] = f'任务目录：{work}\n'+log.read_text(encoding='utf-8',errors='replace')[-3000:]
            time.sleep(1)
    if process.returncode != 0:
        failure = work/'failure.json'
        reason = json.loads(failure.read_text(encoding='utf-8'))['error'] if failure.is_file() else log.read_text(encoding='utf-8',errors='replace')[-2200:]
        raise RuntimeError(f'自动构建未通过，未生成发布包：{reason}\n日志：{log}')


def run(project, blender, job):
    pose = Path(project['files']['poseBlend']).resolve()
    pose.relative_to((ROOT / 'work').resolve())
    if not pose.is_file():
        raise ValueError('姿势文件不存在')
    profile = project['targetProfile']
    if not profile.get('bodySlots'):
        raise ValueError('该角色缺少完整资源映射，未生成 Mod')
    work = ROOT / 'work' / 'replacer_jobs' / uuid.uuid4().hex
    work.mkdir(parents=True)
    snapshot = work / 'input.blend'
    before = digest(pose)
    shutil.copy2(pose, snapshot)
    if digest(snapshot) != before or digest(pose) != before:
        raise ValueError('Blender 正在保存，请保存完成后重试')
    config = dict(project=str(ROOT), work=str(work), input=str(snapshot),
                  originalBlend=str(pose), sourceModel=project['sourceModel'], profile=profile, source_sha256=before)
    (work / 'request.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
    script = ROOT / 'scripts' / 'build_character_mod.py'
    run_blender_stage(blender,script,work/'request.json',work,job,'build')
    if not (work/'validation_request.json').is_file():
        raise RuntimeError('导出未返回本次任务的验证请求')
    # A fresh Blender process cannot reuse source-scene images or stale mesh pointers.
    run_blender_stage(blender,script,work/'validation_request.json',work,job,'validation')
    result = json.loads((work / 'result.json').read_text())
    if not result.get('passed') or result.get('source_sha256') != before:
        raise RuntimeError('构建校验结果不匹配，拒绝打包')
    stage = work / 'package'
    paths = sorted(p for p in stage.rglob('*') if p.is_file())
    if not paths or not (stage / 'modinfo.ini').is_file():
        raise RuntimeError('缺少安装清单')
    folder = package_name(project['sourceModel'], profile['id'], work.name)
    archive = work / (folder+'.zip')
    hashes = package_directory(stage, archive)
    result.update(packageZip=str(archive), archive_sha256=digest(archive), files=hashes,
                  in_game_verified=False, workDir=str(work), ok=True)
    (work / 'release.json').write_text(json.dumps(result, indent=2))
    return result

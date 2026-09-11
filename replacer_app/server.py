import json
import os
import re
import socket
import shutil
import subprocess
import sys
import threading
import time
import uuid
import hashlib
import webbrowser
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import run as build_pipeline
import game_resources
from runtime_paths import find_blender, find_mmd_tools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse, quote


PROJECT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT / "replacer_app" / "web"
APP_DATA = PROJECT / "replacer_app" / "data"
PROJECTS_DB = APP_DATA / "projects.json"
REFERENCE_ROOT = PROJECT / "reference_leon" / "natives" / "stm" / "_chainsaw" / "character" / "ch"
BLENDER = find_blender()
MMD_TOOLS_PARENT = find_mmd_tools()
JOBS = {}
DB_LOCK = threading.RLock()
WORKER_LOCK = threading.Lock()


def source_revision():
    digest = hashlib.sha256()
    # Include imported pipeline code: updating it requires a server restart too.
    for folder, pattern in ((PROJECT / 'replacer_app', '*.py'),
                            (WEB_ROOT, '*'), (PROJECT / 'scripts', '*.py')):
        for path in sorted(folder.glob(pattern)):
            if path.is_file():
                digest.update(path.name.encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


LOADED_REVISION = source_revision()


def launch_worker(worker, *args):
    def serialized():
        with WORKER_LOCK:
            worker(*args)
    threading.Thread(target=serialized, daemon=True).start()


CHARACTER_LABELS = {
    "cha000": "里昂",
    "cha001": "里昂",
    "cha002": "里昂",
    "cha003": "里昂",
    "cha008": "里昂",
}


SLOT_LABELS = {
    "00": "Body",
    "01": "Partial 01",
    "02": "Partial 02",
    "10": "Head/Face",
    "11": "Face Partial",
    "12": "Head Partial",
    "20": "Hair",
    "21": "Hair/Strands",
    "50": "Accessory",
}


def slugify(value):
    value = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value.strip(), flags=re.UNICODE)
    value = value.strip("._")
    return value or "character_replacer"


def json_response(handler, data, status=200):
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def error_response(handler, message, status=400):
    json_response(handler, {"ok": False, "error": message}, status=status)


def process_failed(process):
    output = f"{process.stdout or ''}\n{process.stderr or ''}"
    return process.returncode != 0 or "Traceback (most recent call last):" in output


def extract_last_json(stdout):
    for line in reversed((stdout or "").splitlines()):
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def fail_job(job, message):
    job["status"] = "failed"
    job["error"] = message


def read_projects_db():
    if not PROJECTS_DB.is_file():
        return []
    try:
        return json.loads(PROJECTS_DB.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def write_projects_db(projects):
    APP_DATA.mkdir(parents=True, exist_ok=True)
    with DB_LOCK:
        temporary = PROJECTS_DB.with_suffix('.'+uuid.uuid4().hex+'.tmp')
        temporary.write_text(json.dumps(projects, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, PROJECTS_DB)


def upsert_project(record):
    with DB_LOCK:
        projects = read_projects_db()
        projects = [item for item in projects if item.get("id") != record.get("id")]
        projects.insert(0, record)
        write_projects_db(projects[:100])


def resolve_character_target(target_id):
    if not target_id:
        target_id = "leon"
    if target_id.startswith("cha"):
        for character in scan_replaceable_characters():
            if target_id in character.get("characterIds", []):
                return character
    for character in scan_replaceable_characters():
        if character["id"] == target_id:
            return character
    raise ValueError(f"Unsupported replace target: {target_id}")


def project_record_from_pose_result(result, source_model, character, slot_ids, work_name):
    project_id = slugify(result.get("name") or work_name)
    now = time.time()
    return {
        "id": project_id,
        "name": result.get("name") or work_name,
        "createdAt": now,
        "updatedAt": now,
        "target": character["id"],
        "targetLabel": character["label"],
        "targetProfile": character,
        "internalTarget": character.get("primaryTarget"),
        "slot": result.get("slot") or (slot_ids[0] if slot_ids else "00"),
        "sourceModel": str(source_model),
        "workDir": str(Path(result.get("blend", "")).parent) if result.get("blend") else None,
        "userState": "needs_pose_review",
        "files": {
            "poseBlend": result.get("blend"),
            "poseReport": result.get("report"),
            "previewImage": result.get("previewImage"),
            "previewImages": result.get("previewImages", {}),
            "packageZip": None,
        },
    }


def infer_stage_files(work_dir):
    work_path = Path(work_dir)
    if not work_path.is_dir():
        return {}
    files = {
        "poseBlend": None,
        "poseReport": None,
        "exportBlend": None,
        "mesh": None,
        "packageZip": None,
    }
    pose_blends = sorted(work_path.glob("*POSE_ALIGNMENT.blend"), key=lambda path: path.stat().st_mtime, reverse=True)
    pose_reports = sorted(work_path.glob("*pose_alignment_report.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    export_blends = sorted(work_path.glob("*EXPORT*.blend"), key=lambda path: path.stat().st_mtime, reverse=True)
    meshes = sorted(work_path.glob("*.mesh.*"), key=lambda path: path.stat().st_mtime, reverse=True)
    if pose_blends:
        files["poseBlend"] = str(pose_blends[0])
    if pose_reports:
        files["poseReport"] = str(pose_reports[0])
    if export_blends:
        files["exportBlend"] = str(export_blends[0])
    if meshes:
        files["mesh"] = str(meshes[0])
    return files


def scan_projects():
    known = read_projects_db()
    by_id = {item.get("id"): item for item in known if item.get("id")}

    for report_path in sorted((PROJECT / "work").glob("*/*pose_alignment_report.json"), key=lambda path: path.stat().st_mtime, reverse=True):
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        project_id = slugify(report.get("name") or report_path.parent.name)
        if project_id in by_id:
            continue
        by_id[project_id] = {
            "id": project_id,
            "name": report.get("name") or report_path.parent.name,
            "createdAt": report_path.stat().st_mtime,
            "updatedAt": report_path.stat().st_mtime,
            "target": report.get("target"),
            "slot": report.get("slot"),
            "sourceModel": report.get("sourceModel"),
            "workDir": str(report_path.parent),
            "userState": "needs_pose_review",
            "files": infer_stage_files(report_path.parent),
        }

    projects = list(by_id.values())
    projects.sort(key=lambda item: item.get("updatedAt") or item.get("createdAt") or 0, reverse=True)
    return projects


def scan_targets():
    cha0 = REFERENCE_ROOT / "cha0"
    targets = []
    if not cha0.is_dir():
        return targets

    for char_dir in sorted(path for path in cha0.iterdir() if path.is_dir() and path.name.startswith("cha")):
        slots = []
        skeleton = char_dir.with_suffix(".skeleton.5")
        for slot_dir in sorted(path for path in char_dir.iterdir() if path.is_dir()):
            mesh_files = sorted(slot_dir.glob("*.mesh.*"))
            mdf_files = sorted(slot_dir.glob("*.mdf2.*"))
            if not mesh_files and not mdf_files:
                continue
            slot = {
                "id": slot_dir.name,
                "label": SLOT_LABELS.get(slot_dir.name, f"Slot {slot_dir.name}"),
                "path": str(slot_dir),
                "mesh": str(mesh_files[0]) if mesh_files else None,
                "mdf": str(mdf_files[0]) if mdf_files else None,
                "kind": "body" if slot_dir.name == "00" else "partial",
                "meshSize": mesh_files[0].stat().st_size if mesh_files else None,
                "mdfSize": mdf_files[0].stat().st_size if mdf_files else None,
            }
            slots.append(slot)

        if slots:
            targets.append(
                {
                    "id": char_dir.name,
                    "label": CHARACTER_LABELS.get(char_dir.name, char_dir.name),
                    "path": str(char_dir),
                    "skeleton": str(skeleton) if skeleton.is_file() else None,
                    "slots": slots,
                    "bodySlots": [slot for slot in slots if slot["kind"] == "body"],
                    "partialSlots": [slot for slot in slots if slot["kind"] == "partial"],
                }
            )
    return targets


def scan_replaceable_characters():
    slot_targets = {target["id"]: target for target in scan_targets()}
    characters = []
    scanned = game_resources.read_index()
    for character in game_resources.CHARACTERS:
        item = dict(character)
        item.update(primarySlot='00', verified=False)
        primary_target = item.get("primaryTarget")
        primary_slot = item.get("primarySlot")
        target = slot_targets.get(primary_target)
        primary_slot_data = None
        if target:
            primary_slot_data = next((slot for slot in target.get("slots", []) if slot["id"] == primary_slot), None)
        preset = PROJECT / 'replacer_app/presets' / ('re4_'+item['id']) / 'profile.json'
        policy = json.loads(preset.read_text(encoding='utf-8')) if preset.is_file() else {}
        reference_mesh = policy.get('reference_mesh') or (primary_slot_data or {}).get('mesh')
        item['referenceMesh'] = reference_mesh
        item['bodySlots'] = {cid:['00'] for cid in item['characterIds']
                             if any('/'+cid+'/00/' in path.lower() for path in policy.get('body_meshes',[]))}
        item['available'] = bool(reference_mesh and Path(reference_mesh).is_file() and policy)
        item['description'] = '可生成测试包 · 未经游戏内验收' if item['available'] else '已扫描到资源 · 兼容配置尚不可用'
        item['discovered'] = bool(target or (scanned and any('/'+item['primaryTarget']+'/' in p for p in scanned['resources'])))
        item["reference"] = {
            "target": target,
            "primarySlot": primary_slot_data,
        } if target or reference_mesh else None
        if item['discovered']:
            characters.append(item)
    return characters


def classify_source_model(path):
    name = path.stem.lower()
    local_text = f"{path.name} {path.parent.name}".lower()
    prop_keywords = [
        "刀",
        "枪",
        "子弹",
        "weapon",
        "bullet",
        "sword",
        "gun",
        "blade",
        "katana",
    ]
    character_keywords = [
        "卡芙卡",
        "kafka",
        "人物",
        "角色",
        "character",
        "body",
        "model",
    ]
    if any(keyword in local_text for keyword in prop_keywords):
        return "prop", 0
    score = 10 if path.suffix.lower() in {".pmx", ".pmd", ".fbx", ".blend"} else 0
    score += 40 if any(keyword in local_text for keyword in character_keywords) else 0
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    if size > 1_000_000:
        score += 30
    elif size > 200_000:
        score += 10
    return "character", score


def scan_source_models():
    roots = [PROJECT / "source_model"]
    exts = {".pmx", ".pmd", ".fbx", ".blend"}
    models = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in exts:
                kind, score = classify_source_model(path)
                models.append(
                    {
                        "name": path.name,
                        "path": str(path),
                        "extension": path.suffix.lower(),
                        "size": path.stat().st_size,
                        "modified": path.stat().st_mtime,
                        "kind": kind,
                        "score": score,
                        "recommended": kind == "character" and score >= 40,
                    }
                )
    models.sort(key=lambda item: (item["kind"] != "character", -item["score"], -item["size"], item["name"].lower()))
    return models


def run_job(job_id, payload):
    job = JOBS[job_id]
    try:
        source_model = Path(payload["sourceModel"])
        if not source_model.is_file():
            raise FileNotFoundError(f"Source model not found: {source_model}")
        if not BLENDER.is_file():
            raise FileNotFoundError(f"Blender not found: {BLENDER}")

        project_name = slugify(payload.get("projectName") or source_model.stem)
        character = resolve_character_target(payload.get("targetId"))
        if not character.get("available", character.get("verified")):
            raise ValueError(f"{character['label']} 还没有可用的参考资源")
        target_id = character.get("primaryTarget") or "cha000"
        slot_ids = payload.get("slotIds") or [character.get("primarySlot") or "00"]
        work_name = f"{project_name}_{character['id']}_{uuid.uuid4().hex[:10]}"
        script = PROJECT / "scripts" / "create_pose_alignment_workspace.py"
        args = [
            str(BLENDER),
            "--background",
            "--python-exit-code", "1",
            "--python",
            str(script),
            "--",
            "--project",
            str(PROJECT),
            "--source-model",
            str(source_model),
            "--name",
            work_name,
            "--target",
            target_id,
            "--reference-mesh",
            character['referenceMesh'],
            "--slots",
            ",".join(slot_ids),
            "--mmd-tools-parent",
            str(MMD_TOOLS_PARENT),
        ]
        job["status"] = "running"
        job["command"] = args
        process = subprocess.run(args, cwd=str(PROJECT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        job["stdout"] = process.stdout
        job["stderr"] = process.stderr
        job["returncode"] = process.returncode
        if process_failed(process):
            fail_job(job, "姿势预览失败："+(process.stderr or process.stdout)[-1800:])
            return

        last_json = extract_last_json(process.stdout)
        if not last_json or not last_json.get("ok"):
            fail_job(job, "Blender finished without a success JSON result.")
            return
        job["result"] = last_json or {}
        if job["result"].get("ok"):
            record = project_record_from_pose_result(job["result"], source_model, character, slot_ids, work_name)
            upsert_project(record)
            job["result"]["project"] = record
        job["status"] = "complete"
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)




def run_build_job(job_id, project):
    job = JOBS[job_id]
    job['status'] = 'running'
    try:
        result = build_pipeline(project, BLENDER, job)
        project['lastBuild'] = {key:result[key] for key in ('packageZip','source_sha256','previewImages','experimental','workDir')}
        project['updatedAt'] = time.time()
        upsert_project(project)
        job['result'] = result
        job['status'] = 'complete'
    except Exception as exc:
        fail_job(job, str(exc))


def append_job_progress(job, message):
    previous = job.get('stdout', '')
    job['stdout'] = (previous + ('\n' if previous else '') + message)[-4000:]


def profile_is_current(character, data):
    folder = PROJECT / 'replacer_app' / 'presets' / ('re4_' + character['id'])
    try:
        policy = json.loads((folder / 'profile.json').read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return False
    expected_fingerprint = json.loads(json.dumps(data.get('fingerprint')))
    return (policy.get('character') == character['id']
            and policy.get('game_fingerprint') == expected_fingerprint
            and (folder / 'hidden.mesh.221108797').is_file()
            and (folder / 'neutral.mdf2.32').is_file()
            and all((folder / 'partials' / path).is_file()
                    for path in policy.get('partial_meshes', [])))


def run_scan_job(job_id, payload):
    job = JOBS[job_id]
    job['status'] = 'running'
    try:
        data = game_resources.scan(payload.get('gamePath') or game_resources.DEFAULT_GAME, job)
        job['stdout'] = '游戏索引扫描完成'
        characters = game_resources.CHARACTERS
        pending = [character for character in characters if not profile_is_current(character, data)]
        if pending:
            pending_ids = {value for character in pending for value in character['characterIds']}
            required_paths = [path for path in data['resources']
                              if path in game_resources.COMMON_RESOURCES
                              or any('/' + character_id + '/' in path for character_id in pending_ids)]
            reference = game_resources.CACHE / 'reference'
            game_resources.extract(
                data, required_paths, reference,
                lambda current, total, pak: append_job_progress(job, f'正在提取参考资源 {current}/{total}：{pak}'),
            )
        else:
            append_job_progress(job, '全部角色配置均与当前游戏版本匹配，无需重新提取')
        for index, character in enumerate(characters, 1):
            label = character['label']
            if profile_is_current(character, data):
                append_job_progress(job, f'角色配置 {index}/{len(characters)}：{label} 已完成，跳过')
                continue
            append_job_progress(job, f'正在准备角色配置 {index}/{len(characters)}：{label}')
            command = [str(BLENDER), '-b', '--python-exit-code', '1', '--python',
                       str(PROJECT/'scripts/prepare_character_profiles.py'), '--',
                       '--character', character['id'], '--skip-extract']
            try:
                process = subprocess.run(command, cwd=PROJECT, capture_output=True, text=True,
                                         encoding='utf-8', errors='replace', timeout=180)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f'准备“{label}”角色配置时 Blender 在 180 秒内没有完成。'
                    '请使用 Blender 5.2 LTS 或 4.2，并重试；此前已完成的角色会保留。'
                ) from exc
            if process.stdout:
                append_job_progress(job, process.stdout[-1600:])
            if process_failed(process):
                raise RuntimeError(f'准备“{label}”角色配置失败：'+(process.stderr or process.stdout)[-1600:])
            result = extract_last_json(process.stdout)
            if not result or character['id'] not in result.get('prepared', []):
                if result and character['id'] in result.get('skipped', []):
                    append_job_progress(job, f'未发现“{label}”的主模型资源，已跳过')
                    continue
                raise RuntimeError(f'准备“{label}”角色配置后没有生成有效结果')
            if not profile_is_current(character, data):
                raise RuntimeError(f'“{label}”角色配置输出不完整，已停止以避免使用损坏缓存')
        job.update(status='complete',result={'gamePath':data['game'],'targets':scan_replaceable_characters()})
    except Exception as exc:
        fail_job(job,str(exc))


def default_model_directory():
    candidates = [
        os.environ.get('REPLACER_MODEL_DIR'),
        PROJECT / 'source_model',
        Path.home() / 'Documents',
        Path.home() / 'Desktop',
        Path.home(),
        PROJECT,
    ]
    return next((Path(path).expanduser() for path in candidates if path and Path(path).expanduser().is_dir()), PROJECT)


def browse_model_directory(raw_path=''):
    path = Path(raw_path).expanduser() if raw_path else default_model_directory()
    if not path.is_absolute() or str(path).startswith(('\\\\','//')):
        raise ValueError('请选择本机磁盘上的绝对文件夹路径')
    path = path.resolve(strict=True)
    if not path.is_dir():raise ValueError('这不是文件夹，请选择包含模型的文件夹')
    entries = []
    with os.scandir(path) as listing:
        for entry in listing:
            try:
                directory = entry.is_dir()
                if directory or Path(entry.name).suffix.lower() in {'.pmx','.pmd','.fbx','.blend'}:
                    entries.append(dict(name=entry.name,path=entry.path,directory=directory))
            except OSError:
                continue
            if len(entries)>10000:raise ValueError('文件夹内容过多，请直接输入更具体的子文件夹路径')
    entries.sort(key=lambda e:(not e['directory'],e['name'].casefold()))
    drives = [f'{letter}:/' for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if Path(f'{letter}:/').is_dir()]
    return dict(path=str(path),parent=str(path.parent) if path.parent!=path else None,entries=entries,drives=drives)


def pick_model_with_native_dialog():
    broker_value = os.environ.get('REPLACER_NATIVE_PICKER_DIR', '').strip()
    if broker_value:
        broker = Path(broker_value).resolve()
        try:
            broker.relative_to(APP_DATA.resolve())
        except ValueError as exc:
            raise RuntimeError('系统文件选择器请求目录无效') from exc
        broker.mkdir(parents=True, exist_ok=True)
        request_id = uuid.uuid4().hex
        request_path = broker / f'{request_id}.request.json'
        result_path = broker / f'{request_id}.result.json'
        acknowledgement_path = broker / f'{request_id}.ack'
        temporary = broker / f'{request_id}.{os.getpid()}.tmp'
        try:
            temporary.write_text(json.dumps({'initial': str(default_model_directory())}, ensure_ascii=False), encoding='utf-8')
            os.replace(temporary, request_path)
            acknowledgement_deadline = time.monotonic() + 5
            while not acknowledgement_path.is_file():
                if time.monotonic() >= acknowledgement_deadline:
                    raise RuntimeError('主程序未能打开系统文件窗口，请确认启动器仍在运行')
                time.sleep(.05)
            result_deadline = time.monotonic() + 600
            while not result_path.is_file():
                if time.monotonic() >= result_deadline:
                    raise RuntimeError('系统文件窗口等待超时')
                time.sleep(.05)
            result = json.loads(result_path.read_text(encoding='utf-8-sig'))
            return validate_native_picker_result(result)
        finally:
            for path in (temporary, request_path, result_path, acknowledgement_path):
                path.unlink(missing_ok=True)

    launcher = PROJECT / 'RE4RCharacterReplacer.exe'
    if not launcher.is_file():
        raise FileNotFoundError('系统文件选择器只在完整 EXE 发布包中可用')
    APP_DATA.mkdir(parents=True, exist_ok=True)
    result_path = APP_DATA / f'model-picker-{uuid.uuid4().hex}.json'
    try:
        process = subprocess.run(
            [str(launcher), '--pick-model', '--output', str(result_path), '--initial', str(default_model_directory())],
            cwd=str(PROJECT), timeout=180,
        )
        if not result_path.is_file():
            raise RuntimeError(f'系统文件选择器未返回结果（退出代码 {process.returncode}）')
        result = json.loads(result_path.read_text(encoding='utf-8-sig'))
        return validate_native_picker_result(result)
    finally:
        result_path.unlink(missing_ok=True)


def validate_native_picker_result(result):
    if not result.get('ok'):
        raise RuntimeError(result.get('error') or '系统文件选择器启动失败')
    if result.get('cancelled'):
        return {'cancelled': True}
    selected = Path(result.get('path') or '').resolve(strict=True)
    if not selected.is_file() or selected.suffix.lower() not in {'.pmx', '.pmd', '.fbx', '.blend'}:
        raise ValueError('请选择 PMX、PMD、FBX 或 BLEND 模型文件')
    return {'cancelled': False, 'path': str(selected), 'name': selected.name, 'directory': str(selected.parent)}


def run_refresh_job(job_id, project):
    job = JOBS[job_id]
    job['status'] = 'running'
    try:
        blend = Path(project['files']['poseBlend']).resolve()
        blend.relative_to((PROJECT / 'work').resolve())
        result = subprocess.run([str(BLENDER), '-b', '--python-exit-code', '1', '--python',
                                 str(PROJECT / 'scripts/refresh_pose_preview.py'), '--', str(blend)],
                                cwd=PROJECT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900)
        job['stdout'] = result.stdout[-4000:]
        if result.returncode:
            raise RuntimeError(result.stderr[-4000:] or result.stdout[-4000:])
        views = json.loads((blend.parent / 'saved_preview.json').read_text(encoding='utf-8'))
        project['files'].update(previewImages=views, previewImage=views['front'])
        upsert_project(project)
        job.update(status='complete', result={'project': project})
    except Exception as exc:
        fail_job(job, str(exc))


class ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if os.name == 'nt' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def local_request(self):
        host = self.headers.get('Host', '')
        allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        origin = self.headers.get('Origin')
        if host not in allowed or (origin and origin != 'http://'+host) or self.headers.get('Sec-Fetch-Site') == 'cross-site':
            error_response(self, 'Cross-origin access is not allowed', status=403)
            return False
        return True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, fmt, *args):
        sys.stdout.write("[replacer-app] " + fmt % args + "\n")

    def list_directory(self, path):
        self.send_error(404, 'Directory listing is disabled')
        return None

    def do_GET(self):
        if not self.local_request():
            return
        parsed = urlparse(self.path)
        if parsed.path == '/api/health':
            json_response(self, {'ok': True, 'application': 're4r-replacer',
                                 'revision': LOADED_REVISION,
                                 'current': LOADED_REVISION == source_revision(),
                                 'pid': os.getpid()})
            return
        if parsed.path == "/api/targets":
            index = game_resources.read_index()
            json_response(self, {"ok": True, "targets": scan_replaceable_characters(),
                                 "scanned":bool(index),"gamePath":index['game'] if index else str(game_resources.DEFAULT_GAME)})
            return
        if parsed.path == "/api/models":
            json_response(self, {"ok": True, "models": scan_source_models()})
            return
        if parsed.path == "/api/browse-model":
            error_response(self, '文件选择入口已更新，请刷新页面后点击“选择模型”', status=410)
            return
        if parsed.path == "/api/model-directory":
            try:
                raw_path=(parse_qs(parsed.query).get('path') or [''])[0]
                json_response(self,dict(ok=True,**browse_model_directory(raw_path)))
            except (OSError,ValueError) as exc:
                error_response(self,'无法打开文件夹：'+str(exc),status=400)
            return
        if parsed.path == "/api/projects":
            json_response(self, {"ok": True, "projects": scan_projects()})
            return
        if parsed.path == "/api/jobs":
            query = parse_qs(parsed.query)
            job_id = (query.get("id") or [""])[0]
            if not job_id:
                json_response(self, {"ok": True, "jobs": JOBS})
                return
            job = JOBS.get(job_id)
            if job is None:
                error_response(self, "Job not found", status=404)
                return
            json_response(self, {"ok": True, "job": job})
            return
        if parsed.path == "/api/file":
            query = parse_qs(parsed.query)
            raw_path = (query.get("path") or [""])[0]
            path = Path(unquote(raw_path))
            try:
                resolved = path.resolve()
                resolved.relative_to((PROJECT/'work').resolve())
            except Exception:
                error_response(self, "File is outside project", status=403)
                return
            if not resolved.is_file():
                error_response(self, "File not found", status=404)
                return
            if resolved.suffix.lower() not in ('.png','.zip','.json'):
                error_response(self, "Unsupported download type", status=403)
                return
            content_type = "image/png" if resolved.suffix.lower() == ".png" else "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(resolved.stat().st_size))
            self.send_header("X-Content-Type-Options", "nosniff")
            if resolved.suffix.lower()=='.zip':
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8''"+quote(resolved.name))
            self.end_headers()
            try:
                with resolved.open('rb') as stream:shutil.copyfileobj(stream,self.wfile,1024*1024)
            except (BrokenPipeError,ConnectionResetError):
                pass
            return
        if parsed.path.startswith('/api/'):
            error_response(self, 'Unknown API endpoint', status=404)
            return
        if parsed.path == '/':
            self.path = '/index.html'
        super().do_GET()

    def do_POST(self):
        if not self.local_request():
            return
        if LOADED_REVISION != source_revision():
            error_response(self, '后台需要重启，当前任务未启动。请在启动器中停止并重新启动服务。', status=409)
            return
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= 65536:
                raise ValueError()
        except ValueError:
            error_response(self, 'Invalid request size', status=413)
            return
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            error_response(self, f"Invalid JSON: {exc}")
            return

        if not isinstance(payload, dict):
            error_response(self, 'Expected a JSON object')
            return

        if parsed.path == '/api/pick-model':
            try:
                json_response(self, {'ok': True, **pick_model_with_native_dialog()})
            except (OSError, ValueError, RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
                error_response(self, '无法打开系统文件选择器：' + str(exc), status=500)
            return

        if parsed.path == '/api/scan-game':
            job_id = uuid.uuid4().hex
            JOBS[job_id] = dict(id=job_id,status='queued',createdAt=time.time())
            launch_worker(run_scan_job,job_id,payload)
            json_response(self,{'ok':True,'jobId':job_id})
            return

        if parsed.path == "/api/create-pose-workspace":
            if not payload.get("sourceModel"):
                error_response(self, "sourceModel is required")
                return
            job_id = uuid.uuid4().hex
            JOBS[job_id] = {
                "id": job_id,
                "status": "queued",
                "createdAt": time.time(),
                "payload": payload,
            }
            launch_worker(run_job,job_id,payload)
            json_response(self, {"ok": True, "jobId": job_id})
            return

        if parsed.path == "/api/open-blender":
            blend = payload.get("blend")
            if not blend:
                error_response(self, "blend is required")
                return
            blend_path = Path(blend)
            try:
                blend_path.resolve().relative_to(PROJECT.resolve())
            except Exception:
                error_response(self, "Blend is outside project", status=403)
                return
            if not blend_path.is_file():
                error_response(self, "Blend not found", status=404)
                return
            try:
                if not BLENDER.is_file():
                    raise FileNotFoundError(str(BLENDER))
                process = subprocess.Popen([str(BLENDER), str(blend_path.resolve())], cwd=str(PROJECT))
                try:
                    code = process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    code = None
                if code is not None:
                    raise RuntimeError(f'Blender exited during startup (code {code})')
            except (OSError, RuntimeError) as exc:
                error_response(self, '无法打开 Blender：' + str(exc), status=500)
                return
            json_response(self, {"ok": True, "pid": process.pid, "blend": str(blend_path.resolve())})
            return

        if parsed.path in {"/api/build-mod", "/api/refresh-preview"}:
            project_id = payload.get("projectId")
            project = next((item for item in read_projects_db() if item.get("id") == project_id), None)
            if project is None:
                error_response(self, "Project not found", status=404)
                return
            job_id = uuid.uuid4().hex
            JOBS[job_id] = {
                "id": job_id,
                "status": "queued",
                "createdAt": time.time(),
                "payload": payload,
            }
            worker = run_refresh_job if parsed.path == '/api/refresh-preview' else run_build_job
            launch_worker(worker,job_id,project)
            json_response(self, {"ok": True, "jobId": job_id})
            return


        error_response(self, "Unknown API endpoint", status=404)


def main():
    os.chdir(str(WEB_ROOT))
    port = int(os.environ.get('REPLACER_PORT', '8765'))
    for candidate in range(port,port+20):
        try:
            server = ExclusiveThreadingHTTPServer(("127.0.0.1", candidate), Handler)
            port=candidate
            break
        except OSError as exc:
            if getattr(exc,'winerror',None)!=10048 and exc.errno not in (48,98,10048):raise
    else:
        raise RuntimeError('No free local port; set REPLACER_PORT')
    state_path = Path(os.environ.get('REPLACER_SERVER_STATE', str(PROJECT / 'replacer-server.json')))
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        'pid': os.getpid(),
        'port': port,
        'url': f'http://127.0.0.1:{port}/',
        'startedAt': time.time(),
    }
    temporary_state = state_path.with_name(state_path.name + f'.{os.getpid()}.tmp')
    temporary_state.write_text(json.dumps(state), encoding='utf-8')
    os.replace(temporary_state, state_path)
    print("RE4R Character Replacer Assistant")
    print(f"Open http://127.0.0.1:{port}", flush=True)
    if os.environ.get('REPLACER_OPEN_BROWSER') == '1':
        webbrowser.open(f'http://127.0.0.1:{port}/')
    try:
        server.serve_forever()
    finally:
        server.server_close()
        try:
            current = json.loads(state_path.read_text(encoding='utf-8'))
            if current.get('pid') == os.getpid():
                state_path.unlink(missing_ok=True)
        except (OSError, ValueError, AttributeError):
            pass


if __name__ == "__main__":
    main()

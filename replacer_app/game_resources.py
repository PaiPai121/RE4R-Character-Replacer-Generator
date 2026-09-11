"""Read game archive indexes; extract only explicit character references to cache."""
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path, PurePosixPath
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runtime_paths import find_game, find_resource_list

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT.parent / 'RE4R_KnifeOps_Tools'
HELPER = (ROOT / 'tools/replacer_pak/ReplacerPak.exe' if
          (ROOT / 'tools/replacer_pak/ReplacerPak.exe').is_file() else
          ROOT / 'tools/replacer_pak/bin/Release/net10.0/ReplacerPak.exe')
RESOURCE_LIST = find_resource_list()
CACHE = ROOT / 'work/game_resources'
INDEX = CACHE / 'index.json'
DEFAULT_GAME = find_game()
COMMON_RESOURCES = [
    'natives/stm/systems/rendering/nullwhite.tex.143221013',
    'natives/stm/systems/rendering/nullnormalroughness.tex.143221013',
    'natives/stm/_chainsaw/mastermaterial/textures/nullgrayarray.tex.143221013',
]
# Character identities/slot grouping checked against the modder's file reference:
# https://www.feliciakoevoets.com/file-lists-re.html (RE4R section).
CHARACTERS = [
    dict(id='leon', label='里昂', aliases=['Leon','李昂'], primaryTarget='cha000',
         characterIds=['cha000','cha001','cha002','cha003','cha008']),
    dict(id='ashley', label='艾什莉', aliases=['Ashley'], primaryTarget='cha100',
         characterIds=['cha100','cha101','cha102','cha103','cha104']),
    dict(id='ada', label='艾达', aliases=['Ada'], primaryTarget='cha200', characterIds=['cha200']),
    dict(id='luis', label='路易斯', aliases=['Luis'], primaryTarget='cha300', characterIds=['cha300']),
    dict(id='wesker', label='威斯克', aliases=['Wesker'], primaryTarget='cha600', characterIds=['cha600']),
    dict(id='merchant', label='商人', aliases=['Merchant'], primaryTarget='cha700', characterIds=['cha700']),
]


def safe_resource(value):
    path = PurePosixPath(value.replace('\\','/').lower())
    if path.is_absolute() or '..' in path.parts or ':' in str(path) or not str(path).startswith('natives/stm/'):
        raise ValueError('Invalid resource path')
    return str(path)


def candidates():
    ids = {i for c in CHARACTERS for i in c['characterIds']}
    pattern = re.compile(r'^natives/stm/_chainsaw/character/ch/cha\w/(cha\w{3})(?:/|\.)')
    result = list(COMMON_RESOURCES)
    with RESOURCE_LIST.open(encoding='utf-8-sig') as stream:
        for line in stream:
            path = line.strip().lower().replace('\\','/')
            match = pattern.match(path)
            if match and match[1] in ids and re.search(r'\.(?:mesh\.221108797|mdf2\.32|skeleton\.5)$', path):
                result.append(safe_resource(path))
    return sorted(set(result))


def pak_order(path):
    match = re.search(r'\.patch_(\d+)\.pak$', path.name)
    return int(match[1]) if match else -1


def fingerprint(game):
    return [(p.name, p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(game.glob('re_chunk_000*.pak'), key=pak_order)]


def parse_scan_result(result):
    if result.returncode != 0:
        raise RuntimeError('PAK 索引读取失败：'+(result.stderr or result.stdout)[-1200:])
    try:
        items = json.loads(result.stdout or '[]')
    except (TypeError, json.JSONDecodeError) as error:
        raise RuntimeError('PAK 索引工具返回了无效数据：'+(result.stderr or result.stdout)[-1200:]) from error
    if not isinstance(items, list):
        raise RuntimeError('PAK 索引工具返回的数据格式无效')
    return items


def read_index():
    if not INDEX.is_file():
        return None
    data = json.loads(INDEX.read_text(encoding='utf-8'))
    actual = json.loads(json.dumps(fingerprint(Path(data['game']))))
    return data if actual == data['fingerprint'] else None


def scan(game=DEFAULT_GAME, progress=None):
    game = Path(game).resolve()
    if not (game/'re_chunk_000.pak').is_file():
        raise ValueError('游戏目录缺少 re_chunk_000.pak')
    if not HELPER.is_file():
        raise RuntimeError('缺少 PAK 索引工具，请运行软件安装脚本')
    run = CACHE / uuid.uuid4().hex
    run.mkdir(parents=True)
    resources = {}
    paths = candidates()
    initial = fingerprint(game)
    for filename, _, _ in initial:
        if progress is not None:
            progress['stdout'] = '扫描游戏资源索引：'+filename
        # Bounded command length, and only the archive table is read in scan mode.
        for start in range(0,len(paths),100):
            result = subprocess.run([str(HELPER),'--scan',str(game/filename),'-',*paths[start:start+100]],
                                    capture_output=True, text=True, timeout=120)
            for item in parse_scan_result(result):
                path = safe_resource(item['path'])
                resources[path] = dict(item, pak=filename)
    if initial != fingerprint(game):
        raise RuntimeError('游戏文件在扫描期间发生变化，请更新完成后重试')
    data = dict(game=str(game),fingerprint=initial,resources=resources)
    temporary = run/'index.json'
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temporary,INDEX)
    return data


def extract(data, paths, destination, progress=None):
    destination = Path(destination).resolve()
    destination.relative_to((ROOT/'work').resolve())
    groups = {}
    for path in paths:
        path = safe_resource(path)
        entry = data['resources'].get(path)
        if not entry:
            raise ValueError('游戏资源不存在：'+path)
        if entry['size'] > 256*1024*1024:
            raise ValueError('单个参考资源超出大小限制')
        groups.setdefault(entry['pak'],[]).append(path)
    batches = [(pak, entries[start:start+60]) for pak, entries in groups.items()
               for start in range(0,len(entries),60)]
    for index, (pak, batch) in enumerate(batches, 1):
        if progress is not None:
            progress(index, len(batches), pak)
        try:
            process = subprocess.run([str(HELPER),str(Path(data['game'])/pak),str(destination),*batch],
                                     capture_output=True,text=True,timeout=180)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f'参考资源提取在 180 秒内没有完成：{pak}（批次 {index}/{len(batches)}）') from exc
        if process.returncode != 0 or any(not (destination/p).is_file() for p in batch):
            raise RuntimeError('参考资源提取失败：'+(process.stderr or process.stdout)[-1000:])
    return destination


if __name__ == '__main__':
    data = scan()
    print(json.dumps(dict(game=data['game'],resources=len(data['resources'])),ensure_ascii=False))

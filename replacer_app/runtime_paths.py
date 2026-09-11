"""Portable runtime discovery for the public preview package."""
import json
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def blender_version_problem(version):
    version = tuple(int(value) for value in version[:3])
    if version < (4, 3, 2):
        return '需要 Blender 4.3.2 或更新版本。'
    if version[:2] == (5, 1):
        return ('Blender 5.1 存在已知的网格导入/导出严重性能故障，可能导致任务长时间无响应。'
                '请改用 Blender 5.2 LTS 或 Blender 5.0。')
    return None


def _saved_paths():
    config = ROOT / 'replacer-paths.json'
    try:
        data = json.loads(config.read_text(encoding='utf-8-sig'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _first_file(paths):
    return next((Path(path).resolve() for path in paths if path and Path(path).is_file()), None)


def find_blender():
    configured = os.environ.get('REPLACER_BLENDER')
    saved = _saved_paths().get('blender')
    command = shutil.which('blender')
    running_binary = Path(sys.executable) if Path(sys.executable).name.lower() == 'blender.exe' else None
    candidates = [configured, saved, running_binary, ROOT / 'blender' / 'blender.exe', command]
    program_files = Path(os.environ.get('ProgramFiles', r'C:\Program Files'))
    candidates.extend(sorted((program_files / 'Blender Foundation').glob('Blender */blender.exe'),
                             reverse=True))
    for drive in ('C:', 'D:', 'E:', 'F:', 'G:'):
        root = Path(drive + '\\')
        candidates.extend([
            root / 'SteamLibrary/steamapps/common/Blender/blender.exe',
            root / 'Program Files (x86)/Steam/steamapps/common/Blender/blender.exe',
        ])
    return _first_file(candidates) or Path(configured or ROOT / 'blender' / 'blender.exe')


def find_mmd_tools():
    configured = os.environ.get('REPLACER_MMD_TOOLS')
    candidates = [configured, ROOT / 'vendor' / 'blender_mmd_tools',
                  ROOT.parent / 'AssetForge/external/blender_mmd_tools-4.5.11']
    return next((Path(path).resolve() for path in candidates
                 if path and (Path(path) / 'mmd_tools/__init__.py').is_file()),
                Path(configured or ROOT / 'vendor' / 'blender_mmd_tools'))


def find_resource_list():
    configured = os.environ.get('RE4_RESOURCE_LIST')
    candidates = [configured, ROOT / 'data' / 'RE4_STM_Character.list',
                  ROOT.parent / 'RE4R_KnifeOps_Tools/RE4_STM_Release.list']
    return _first_file(candidates) or Path(configured or candidates[1])


def find_game():
    configured = os.environ.get('RE4_GAME_DIR')
    saved = _saved_paths().get('game')
    candidates = [configured, saved]
    for drive in ('C:', 'D:', 'E:', 'F:', 'G:'):
        root = Path(drive + '\\')
        candidates.extend([
            root / 'SteamLibrary/steamapps/common/RESIDENT EVIL 4  BIOHAZARD RE4',
            root / 'Program Files (x86)/Steam/steamapps/common/RESIDENT EVIL 4  BIOHAZARD RE4',
        ])
    return next((Path(path).resolve() for path in candidates
                 if path and (Path(path) / 're_chunk_000.pak').is_file()),
                Path(configured or saved or
                     r'C:\SteamLibrary\steamapps\common\RESIDENT EVIL 4  BIOHAZARD RE4'))

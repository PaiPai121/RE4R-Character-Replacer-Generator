"""Read-only dependency check for the local character replacer."""
import os
import sys
from pathlib import Path
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runtime_paths import blender_version_problem, find_blender, find_game, find_mmd_tools, find_resource_list
ROOT = Path(__file__).resolve().parents[1]
version_problem = blender_version_problem(bpy.app.version)
print(('UNSUPPORTED ' + version_problem) if version_problem else 'OK Blender version: ' + bpy.app.version_string)
checks = {
    'Blender':find_blender(),
    'MMD importer':find_mmd_tools()/'mmd_tools/__init__.py',
    'RE Mesh Editor':ROOT/'tools/RE-Mesh-Editor/__init__.py',
    'PAK helper':(ROOT/'tools/replacer_pak/ReplacerPak.exe' if
                  (ROOT/'tools/replacer_pak/ReplacerPak.exe').is_file() else
                  ROOT/'tools/replacer_pak/bin/Release/net10.0/ReplacerPak.exe'),
    'Game resource list':find_resource_list(),
}
for name,path in checks.items():print(('OK ' if path.is_file() else 'MISSING ')+name+': '+str(path))
game = find_game()
print(('OK ' if (game/'re_chunk_000.pak').is_file() else 'OPTIONAL MISSING ')+'Game: '+str(game))
sys.exit(0 if not version_problem and all(path.is_file() for path in checks.values()) else 1)

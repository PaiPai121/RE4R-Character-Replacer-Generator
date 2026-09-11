"""Create a multi-map fixture from a known-good job, then build and validate it."""
import json
import os
import shutil
import sys
from pathlib import Path

import bpy

ROOT = Path(os.environ.get('REPLACER_TEST_ROOT', Path(__file__).resolve().parents[1])).resolve()
sys.path.insert(0, str(ROOT / 'scripts'))
import build_character_mod as build


def add_generated_image(tree, name, color, color_space):
    image = bpy.data.images.new(name, width=4, height=4, alpha=True)
    image.filepath = name
    image.colorspace_settings.name = color_space
    image.pixels[:] = list(color) * 16
    node = tree.nodes.new('ShaderNodeTexImage')
    node.image = image
    return node


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    if len(args) != 3:
        raise SystemExit('usage: -- SOURCE_INPUT.blend SOURCE_REQUEST.json OUTPUT_WORK')
    source_blend, source_request, work = map(Path, args)
    work = work.resolve()
    allowed = (ROOT / 'work').resolve()
    work.relative_to(allowed)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    bpy.ops.wm.open_mainfile(filepath=str(source_blend.resolve()))
    source = next(obj for obj in bpy.data.objects
                  if obj.type == 'MESH' and obj.name.startswith('SOURCE_MODEL__'))
    material = source.data.materials[0]
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    shader = tree.nodes.new('ShaderNodeBsdfPrincipled')
    shader.name = '用户重命名的原理化节点'
    output = tree.nodes.new('ShaderNodeOutputMaterial')
    tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])

    group_tree = bpy.data.node_groups.new('RegressionMultiMap', 'ShaderNodeTree')
    group_tree.interface.new_socket(name='Color', in_out='OUTPUT', socket_type='NodeSocketColor')
    group_output = group_tree.nodes.new('NodeGroupOutput')
    albedo = add_generated_image(group_tree, 'Head_C.png', (0.7, 0.25, 0.12, 1.0), 'sRGB')
    add_generated_image(group_tree, 'Head_CSAR.png', (0.3, 0.3, 0.3, 1.0), 'Non-Color')
    add_generated_image(group_tree, 'Head_MRA.png', (0.5, 0.1, 0.0, 1.0), 'Non-Color')
    add_generated_image(group_tree, 'Head_N.png', (0.5, 0.5, 1.0, 1.0), 'Non-Color')
    group_tree.links.new(albedo.outputs['Color'], group_output.inputs['Color'])
    group = tree.nodes.new('ShaderNodeGroup')
    group.node_tree = group_tree
    tree.links.new(group.outputs['Color'], shader.inputs['Base Color'])
    material_name = material.name

    fixture = work / 'input.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(fixture))
    config = json.loads(source_request.read_text(encoding='utf-8'))
    config.update(project=str(ROOT), work=str(work), input=str(fixture),
                  originalBlend=str(fixture))
    (work / 'request.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
    build.main(config)
    validation = json.loads((work / 'validation_request.json').read_text(encoding='utf-8'))
    build.validate_export(validation)
    result = json.loads((work / 'result.json').read_text(encoding='utf-8'))
    if not result.get('passed'):
        raise RuntimeError('full build regression did not pass')
    print('FULL_BUILD_REGRESSION=PASS')
    print('MATERIAL=' + material_name)
    print('BASE_IMAGE=Head_C.png')
    print('RESULT=' + str(work / 'result.json'))


if __name__ == '__main__':
    main()

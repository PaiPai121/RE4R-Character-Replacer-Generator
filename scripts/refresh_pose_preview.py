import json
import sys
from pathlib import Path
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
import create_pose_alignment_workspace as pose

path = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
sys.path.insert(0, pose.DEFAULT_MMD_TOOLS_PARENT)
import mmd_tools
mmd_tools.register()
bpy.ops.wm.open_mainfile(filepath=str(path))
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('SOURCE_MODEL__')]
if not meshes:
    raise RuntimeError('Saved workspace has no source meshes')
target = next(o for o in bpy.data.objects if o.type=='ARMATURE' and 'REFERENCE_ARMATURE' in o.name)
source_arms = [o for o in bpy.data.objects if o.type=='ARMATURE' and o != target]
pose.add_source_guides(source_arms,target)
for o in list(bpy.data.objects):
    if o.name.startswith(('POSE_PREVIEW_CAMERA', 'POSE_PREVIEW_AREA_LIGHT')):
        bpy.data.objects.remove(o, do_unlink=True)
for mat in bpy.data.materials:
    if mat.name.startswith('Guide_'):
        mat.use_nodes = True
        shader = mat.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value = mat.diffuse_color
        shader.inputs['Emission Color'].default_value = mat.diffuse_color
        shader.inputs['Emission Strength'].default_value = .5
views = pose.setup_preview_camera(meshes, meshes, path.parent, path.stem + '_saved')
(path.parent / 'saved_preview.json').write_text(json.dumps(views), encoding='utf-8')

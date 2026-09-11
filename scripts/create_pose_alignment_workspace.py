import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import bpy
from mathutils import Vector, Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
from humanoid_bones import mapped_bones, select_source_bones


DEFAULT_PROJECT = str(Path(__file__).resolve().parents[1])
_ROOT = Path(DEFAULT_PROJECT)
_BUNDLED_MMD = _ROOT / 'vendor' / 'blender_mmd_tools'
DEFAULT_MMD_TOOLS_PARENT = os.environ.get(
    'REPLACER_MMD_TOOLS',
    str(_BUNDLED_MMD if (_BUNDLED_MMD / 'mmd_tools/__init__.py').is_file()
        else _ROOT.parent / 'AssetForge/external/blender_mmd_tools-4.5.11'))

ARM_CHAINS = {
    "L": ["L_Shoulder", "L_UpperArm", "L_Forearm", "L_Hand"],
    "R": ["R_Shoulder", "R_UpperArm", "R_Forearm", "R_Hand"],
}

LEG_CHAINS = {
    "L": ["L_Thigh", "L_Shin", "L_Foot", "L_Toe", "L_ToeEnd"],
    "R": ["R_Thigh", "R_Shin", "R_Foot", "R_Toe", "R_ToeEnd"],
}

FINGER_CHAINS = {
    "L": [
        ["L_Hand", "L_Thumb1", "L_Thumb2", "L_Thumb3"],
        ["L_Hand", "L_IndexF1", "L_IndexF2", "L_IndexF3"],
        ["L_Hand", "L_MiddleF1", "L_MiddleF2", "L_MiddleF3"],
        ["L_Hand", "L_RingF1", "L_RingF2", "L_RingF3"],
        ["L_Hand", "L_PinkyF1", "L_PinkyF2", "L_PinkyF3"],
    ],
    "R": [
        ["R_Hand", "R_Thumb1", "R_Thumb2", "R_Thumb3"],
        ["R_Hand", "R_IndexF1", "R_IndexF2", "R_IndexF3"],
        ["R_Hand", "R_MiddleF1", "R_MiddleF2", "R_MiddleF3"],
        ["R_Hand", "R_RingF1", "R_RingF2", "R_RingF3"],
        ["R_Hand", "R_PinkyF1", "R_PinkyF2", "R_PinkyF3"],
    ],
}

TORSO_CHAIN = ["Hip", "Spine_0", "Spine_1", "Spine_2", "Neck_0", "Head"]


def slugify(value):
    value = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value.strip(), flags=re.UNICODE)
    return value.strip("._") or "pose_workspace"


def register_local_package(name, package_dir):
    package_dir = str(package_dir)
    init_py = os.path.join(package_dir, "__init__.py")
    spec = importlib.util.spec_from_file_location(name, init_py, submodule_search_locations=[package_dir])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    if hasattr(module, "register"):
        module.register()
    return module


def bounds(objects):
    points = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    if not points:
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    return (
        Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))),
        Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))),
    )


def import_target_body(project, target, slot, reference_mesh=None):
    re_mesh_editor = register_local_package("re_mesh_editor", str(project / "tools" / "RE-Mesh-Editor"))
    mesh_path = (
        project
        / "reference_leon"
        / "natives"
        / "stm"
        / "_chainsaw"
        / "character"
        / "ch"
        / "cha0"
        / target
        / slot
        / f"{target}_{slot}.mesh.221108797"
    )
    if reference_mesh:
        mesh_path = Path(reference_mesh)
    if not mesh_path.is_file():
        raise FileNotFoundError(f"Target mesh not found: {mesh_path}")

    options = {
        "clearScene": False,
        "createCollections": True,
        "loadMaterials": False,
        "loadMDFData": False,
        "loadShellFur": False,
        "loadUnusedTextures": False,
        "loadUnusedProps": False,
        "useBackfaceCulling": False,
        "reloadCachedTextures": False,
        "mdfPath": "",
        "importAllLODs": False,
        "importBlendShapes": True,
        "rotate90": True,
        "mergeArmature": "",
        "importArmatureOnly": False,
        "mergeGroups": False,
        "importShadowMeshes": False,
        "importOcclusionMeshes": False,
        "importBoundingBoxes": False,
    }
    re_mesh_editor.importREMeshFile(str(mesh_path), options)
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("Target armature was not imported.")
    armature = armatures[0]
    armature.name = f"{target}_{slot}_REFERENCE_ARMATURE_DO_NOT_EDIT"
    armature.show_in_front = True
    return mesh_path, armature


def import_source_model(model_path, mmd_tools_parent, initial_scale):
    suffix = model_path.suffix.lower()
    before = set(bpy.data.objects.keys())
    if suffix in {".pmx", ".pmd"}:
        if str(mmd_tools_parent) not in sys.path:
            sys.path.insert(0, str(mmd_tools_parent))
        import mmd_tools

        mmd_tools.register()
        bpy.ops.mmd_tools.import_model(
            filepath=str(model_path),
            types={"MESH", "ARMATURE", "MORPHS"},
            scale=initial_scale,
            clean_model=False,
            remove_doubles=False,
            log_level="ERROR",
        )
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(model_path))
    elif suffix == ".obj":
        bpy.ops.wm.obj_import(filepath=str(model_path))
    elif suffix == ".blend":
        with bpy.data.libraries.load(str(model_path), link=False) as (data_from, data_to):
            data_to.objects = data_from.objects
        source_collection = bpy.data.collections.new("SOURCE_BLEND_IMPORT")
        bpy.context.scene.collection.children.link(source_collection)
        for obj in data_to.objects:
            if obj is not None:
                source_collection.objects.link(obj)
    else:
        raise RuntimeError(f"Unsupported source model format for MVP: {suffix}")

    imported = [bpy.data.objects[name] for name in set(bpy.data.objects.keys()) - before]
    meshes = [obj for obj in imported if obj.type == "MESH"]
    armatures = [obj for obj in imported if obj.type == "ARMATURE"]
    if not meshes:
        raise RuntimeError("No source mesh was imported.")
    for obj in meshes:
        obj.name = "SOURCE_MODEL__" + obj.name
    for obj in armatures:
        obj.name = "SOURCE_ARMATURE_EDIT_POSE__" + obj.name
        obj.show_in_front = True
    return imported, meshes, armatures


def create_collection(name):
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def configure_preview_material(mat, color):
    mat.diffuse_color = color
    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    # Node display names are user-editable and can be localized.  Blender's node
    # type is the stable API contract, so never rely on "Principled BSDF" here.
    shader = next((node for node in nodes if node.type == 'BSDF_PRINCIPLED'), None)
    if shader is None:
        shader = nodes.new('ShaderNodeBsdfPrincipled')
    output = next((node for node in nodes if node.type == 'OUTPUT_MATERIAL'), None)
    if output is None:
        output = nodes.new('ShaderNodeOutputMaterial')

    surface = next((socket for socket in output.inputs if socket.name == 'Surface'), None)
    bsdf = next((socket for socket in shader.outputs if socket.name == 'BSDF'), None)
    if surface is not None and bsdf is not None and not any(
            link.from_node == shader and link.to_socket == surface for link in tree.links):
        tree.links.new(bsdf, surface)

    def set_input(value, *names):
        socket = next((socket for socket in shader.inputs if socket.name in names), None)
        if socket is not None:
            socket.default_value = value

    set_input(color, 'Base Color')
    # Blender 4+ calls this Emission Color; older supported files may expose Emission.
    set_input(color, 'Emission Color', 'Emission')
    set_input(.5, 'Emission Strength')
    return mat


def create_material(name, color):
    return configure_preview_material(bpy.data.materials.new(name), color)


def bone_point(armature, bone_name, tail=False):
    bone = armature.data.bones.get(bone_name)
    if bone is None:
        return None
    local = bone.tail_local if tail else bone.head_local
    return armature.matrix_world @ local


def chain_points(armature, names):
    points = []
    existing = []
    for name in names:
        point = bone_point(armature, name, tail=False)
        if point is not None:
            points.append(point)
            existing.append(name)
    if existing:
        tail = bone_point(armature, existing[-1], tail=True)
        if tail is not None:
            points.append(tail)
    return existing, points


def link_only(obj, collection):
    collection.objects.link(obj)
    for old in list(obj.users_collection):
        if old != collection:
            old.objects.unlink(obj)


def make_line(collection, name, points, material, bevel_depth=0.006):
    if len(points) < 2:
        return None
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, loc in zip(spline.points, points):
        point.co = (loc.x, loc.y, loc.z, 1.0)
    obj = bpy.data.objects.new(name, curve)
    obj.data.materials.append(material)
    link_only(obj, collection)
    return obj


def make_marker(collection, name, loc, material, radius=0.014):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=radius, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    link_only(obj, collection)
    return obj


def add_guides(armature):
    collection = create_collection("POSE_ALIGNMENT_GUIDES_TARGET")
    mats = {
        "left": create_material("Guide_Left_Red", (1.0, 0.05, 0.03, 1.0)),
        "right": create_material("Guide_Right_Blue", (0.05, 0.25, 1.0, 1.0)),
        "torso": create_material("Guide_Torso_Gold", (1.0, 0.72, 0.08, 1.0)),
        "finger": create_material("Guide_Finger_White", (0.95, 0.95, 0.9, 1.0)),
    }
    report = {}

    existing, points = chain_points(armature, TORSO_CHAIN)
    make_line(collection, "TARGET_Torso_Hip_To_Head", points, mats["torso"], bevel_depth=0.008)
    report["torso"] = existing

    for side, chain in ARM_CHAINS.items():
        existing, points = chain_points(armature, chain)
        mat = mats["left" if side == "L" else "right"]
        make_line(collection, f"TARGET_{side}_Arm", points, mat, bevel_depth=0.009)
        for index, point in enumerate(points):
            make_marker(collection, f"TARGET_{side}_Arm_Marker_{index}", point, mat)
        report[f"{side}_arm"] = existing

    for side, chain in LEG_CHAINS.items():
        existing, points = chain_points(armature, chain)
        mat = mats["left" if side == "L" else "right"]
        make_line(collection, f"TARGET_{side}_Leg", points, mat, bevel_depth=0.009)
        for index, point in enumerate(points):
            make_marker(collection, f"TARGET_{side}_Leg_Marker_{index}", point, mat)
        report[f"{side}_leg"] = existing

    for side, chains in FINGER_CHAINS.items():
        mat = mats["finger"]
        for finger_index, chain in enumerate(chains, start=1):
            existing, points = chain_points(armature, chain)
            make_line(collection, f"TARGET_{side}_Finger_{finger_index}", points, mat, bevel_depth=0.003)
            report[f"{side}_finger_{finger_index}"] = existing

    return report


def render_preview_with_guides():
    scene = bpy.context.scene
    camera = scene.camera
    bpy.context.view_layer.update()
    direction = camera.matrix_world.to_quaternion() @ Vector((0,0,-1))
    plane = camera.location+direction*max(camera.data.clip_start*4,.1)
    projection = Matrix.Identity(4)
    for row in range(3):
        for column in range(3):projection[row][column] -= direction[row]*direction[column]
        projection[row][3] = direction[row]*direction.dot(plane)
    guides = {obj:obj.matrix_world.copy() for collection in bpy.data.collections
              if collection.name.startswith('POSE_ALIGNMENT_GUIDES') for obj in collection.objects}
    saved_points = []
    try:
        # Orthographic projection keeps the exact joint positions while removing occlusion.
        for obj,matrix in guides.items():
            overlay = projection.copy()
            if obj.name.startswith('SOURCE_'):
                overlay.translation -= direction*.025
            if obj.type=='CURVE':
                transform = matrix.inverted() @ overlay @ matrix
                for spline in obj.data.splines:
                    for point in spline.points:
                        saved_points.append((point,point.co.copy()))
                        point.co=transform @ point.co
            else:
                moved = matrix.copy()
                moved.translation = overlay @ matrix.translation
                obj.matrix_world=moved
        bpy.context.view_layer.update()
        bpy.ops.render.render(write_still=True)
    finally:
        for point,coordinate in saved_points:point.co=coordinate
        for obj,matrix in guides.items():obj.matrix_world=matrix
        bpy.context.view_layer.update()


def setup_preview_camera(target_meshes, source_meshes, work_dir, name):
    target_min, target_max = bounds(target_meshes)
    source_min, source_max = bounds(source_meshes)
    min_v = Vector((
        min(target_min.x, source_min.x),
        min(target_min.y, source_min.y),
        min(target_min.z, source_min.z),
    ))
    max_v = Vector((
        max(target_max.x, source_max.x),
        max(target_max.y, source_max.y),
        max(target_max.z, source_max.z),
    ))
    center = (min_v + max_v) * 0.5
    height = max(max_v.z - min_v.z, 1.0)

    bpy.ops.object.light_add(type="AREA", location=(center.x - 1.8, center.y - 3.0, center.z + height * 1.2))
    light = bpy.context.object
    light.name = "POSE_PREVIEW_AREA_LIGHT"
    light.data.energy = 450
    light.data.size = 4.0

    bpy.ops.object.camera_add(location=(center.x, center.y - height * 2.25, center.z + height * 0.55), rotation=(1.32, 0, 0))
    camera = bpy.context.object
    camera.name = "POSE_PREVIEW_CAMERA"
    bpy.context.scene.camera = camera

    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            bpy.context.scene.render.engine = engine
            break
        except TypeError:
            continue
    else:
        raise RuntimeError('Textured preview requires Eevee')
    bpy.context.scene.render.resolution_x = 1000
    bpy.context.scene.render.resolution_y = 1200
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = height*1.22
    bpy.context.scene.render.film_transparent = True
    bpy.context.scene.render.image_settings.color_mode = 'RGBA'
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z','Y').to_euler()
    bpy.context.scene.view_settings.view_transform = "AgX"
    bpy.context.scene.world.color = (.025, .025, .025)
    preview_path = Path(work_dir) / f"{name}_pose_preview.png"
    bpy.context.scene.render.filepath = str(preview_path)
    render_preview_with_guides()
    views = {'front': str(preview_path)}
    camera.location = (center.x,center.y+height*2.25,center.z+height*.2)
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z','Y').to_euler()
    back = Path(work_dir)/f'{name}_back.png'
    bpy.context.scene.render.filepath = str(back)
    render_preview_with_guides()
    views['back'] = str(back)
    camera.location = (center.x+height*2.25, center.y, center.z)
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z','Y').to_euler()
    side = Path(work_dir) / f'{name}_side.png'
    bpy.context.scene.render.filepath = str(side)
    render_preview_with_guides()
    views['side'] = str(side)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and 'REFERENCE_ARMATURE' in o.name)
    for side, key in [('L','hands'),('R','rightHand')]:
        hand = bone_point(arm, side+'_Hand')
        if hand is None:continue
        camera.data.ortho_scale = height*.24
        camera.location = hand + Vector((0,-height*.42,height*.15))
        camera.rotation_euler = (hand-camera.location).to_track_quat('-Z','Y').to_euler()
        path = Path(work_dir) / f'{name}_{key}.png'
        bpy.context.scene.render.filepath = str(path)
        render_preview_with_guides()
        views[key] = str(path)
    camera.data.ortho_scale = height*1.22
    return views


def source_landmarks(source_armatures, target_armature):
    meshes = [o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('SOURCE_MODEL__')]
    selected = select_source_bones(source_armatures,target_armature,meshes)
    return {name:arm.matrix_world @ bone.head for name,(arm,bone) in selected.items()}


def add_source_guides(source_armatures, target_armature):
    for collection in list(bpy.data.collections):
        if collection.name.startswith('POSE_ALIGNMENT_GUIDES_SOURCE'):
            for obj in list(collection.objects):bpy.data.objects.remove(obj,do_unlink=True)
            bpy.data.collections.remove(collection)
    collection = create_collection('POSE_ALIGNMENT_GUIDES_SOURCE')
    mat = create_material('Guide_Source_Green', (.12,.9,.55,1))
    points = source_landmarks(source_armatures,target_armature)
    chains = list(ARM_CHAINS.values())+list(LEG_CHAINS.values())
    chains += [chain for side in FINGER_CHAINS.values() for chain in side]
    errors = {}
    for index, chain in enumerate(chains):
        locations = [points[n] for n in chain if n in points]
        make_line(collection,'SOURCE_Axis_'+str(index),locations,mat,bevel_depth=.0025)
        for name in chain:
            target_point = bone_point(target_armature,name)
            if name in points and target_point is not None:
                errors[name] = (points[name]-target_point).length
    return errors


def fit_source_near_target(source_meshes, target_meshes, source_armatures=(), target_armature=None):
    source_min, source_max = bounds(source_meshes)
    target_min, target_max = bounds(target_meshes)
    source_height = source_max.z - source_min.z
    target_height = target_max.z - target_min.z
    scale = target_height / source_height if source_height else 1.0
    landmarks = source_landmarks(source_armatures,target_armature) if target_armature else {}
    anchors = ('Head','L_Foot','R_Foot')
    skeletal_fit = all(n in landmarks and target_armature.data.bones.get(n) for n in anchors)
    if skeletal_fit:
        source_feet = (landmarks['L_Foot']+landmarks['R_Foot'])*.5
        target_feet = (bone_point(target_armature,'L_Foot')+bone_point(target_armature,'R_Foot'))*.5
        source_span = landmarks['Head'].z-source_feet.z
        target_span = bone_point(target_armature,'Head').z-target_feet.z
        skeletal_fit = source_span > .001 and target_span > .001
        if skeletal_fit:scale = target_span/source_span
    # Transform the imported hierarchy once, including its armature and IK controls.
    roots = set()
    for obj in source_meshes:
        while obj.parent:
            obj = obj.parent
        roots.add(obj)
    for obj in roots:
        obj.scale *= scale
    bpy.context.view_layer.update()

    source_min, source_max = bounds(source_meshes)
    source_center = (source_min + source_max) * 0.5
    target_center = (target_min + target_max) * 0.5
    delta = Vector((target_center.x - source_center.x, target_center.y - source_center.y, target_min.z - source_min.z))
    if skeletal_fit:
        landmarks = source_landmarks(source_armatures,target_armature)
        delta = target_feet-(landmarks['L_Foot']+landmarks['R_Foot'])*.5
    for obj in roots:
        obj.location += delta
    return {
        "scale": scale,
        "method": "head_foot_landmarks" if skeletal_fit else "mesh_bounds",
        "delta": [delta.x, delta.y, delta.z],
        "sourceHeightBefore": source_height,
        "targetHeight": target_height,
    }


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--source-model", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--target", default="cha000")
    parser.add_argument("--reference-mesh")
    parser.add_argument("--slots", default="00")
    parser.add_argument("--mmd-tools-parent", default=DEFAULT_MMD_TOOLS_PARENT)
    parser.add_argument("--initial-pmx-scale", type=float, default=0.08)
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    project = Path(args.project)
    source_model = Path(args.source_model)
    name = slugify(args.name)
    body_slot = (args.slots.split(",") or ["00"])[0].strip() or "00"
    work_dir = project / "work" / name
    work_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    target_mesh_path, armature = import_target_body(project, args.target, body_slot, args.reference_mesh)
    target_meshes = [obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith("Group_")]
    imported, source_meshes, source_armatures = import_source_model(source_model, Path(args.mmd_tools_parent), args.initial_pmx_scale)
    for image in bpy.data.images:
        if image.source == 'FILE' and image.filepath and not image.packed_file:
            if image.filepath.startswith('//'):
                image.filepath = bpy.path.abspath(image.filepath,start=str(source_model.parent))
            # MMD shared toon ramp names may be virtual and unused by the export shader.
            if Path(image.filepath).is_file():
                image.pack()
    fit_report = fit_source_near_target(source_meshes, target_meshes, source_armatures, armature)
    bpy.context.view_layer.update()
    from align_humanoid import align
    alignment_report = align(source_armatures,armature,source_meshes)
    guide_report = add_guides(armature)
    guide_report['sourceDeviation'] = add_source_guides(source_armatures,armature)
    for obj in target_meshes:
        obj.display_type = "WIRE"
        obj.hide_render = True
    preview_images = setup_preview_camera(target_meshes, source_meshes, work_dir, name)
    for obj in source_armatures:
        obj.show_in_front = True

    report = {
        "ok": True,
        "name": name,
        "target": args.target,
        "slot": body_slot,
        "targetMesh": str(target_mesh_path),
        "sourceModel": str(source_model),
        "sourceMeshes": len(source_meshes),
        "sourceArmatures": [obj.name for obj in source_armatures],
        "fit": fit_report,
        "alignment": alignment_report,
        "guides": guide_report,
        "manualCheckpoint": [
            "Open the blend file.",
            "Adjust the source armature/model pose to match the colored target guides.",
            "Red/blue: target left/right arms and legs.",
            "White: target fingers and hand spread.",
            "Gold: torso/head center line.",
            "Save the blend when the source pose matches the target rest pose.",
        ],
        "previewImage": preview_images['front'],
        "previewImages": preview_images,
    }
    blend_path = work_dir / f"{name}_POSE_ALIGNMENT.blend"
    report_path = work_dir / f"{name}_pose_alignment_report.json"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    report["blend"] = str(blend_path)
    report["report"] = str(report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])

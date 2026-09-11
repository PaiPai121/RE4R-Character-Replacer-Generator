"""Deterministic deformation checks on the re-imported mesh, not the source blend."""
import math
import json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector, Matrix


def swing(armature,name,degrees):
    bone = armature.pose.bones[name]
    head = armature.matrix_world @ bone.head
    if name.startswith(('L_','R_')):
        side = name[:2]
        next_name = {'UpperArm':'Forearm','Forearm':'Hand','Thigh':'Shin','Shin':'Foot'}.get(name[2:])
        following = armature.pose.bones.get(side+next_name) if next_name else None
        end = armature.matrix_world @ (following.head if following else bone.tail)
        desired = Vector((1 if name.startswith('L_') else -1,0,0)) if name.endswith('UpperArm') else Vector((0,-1,0))
        axis = (end-head).cross(desired)
        if axis.length < 1e-8:axis=Vector((1,0,0))
        angle = next(d for d in degrees if d)
        if name.endswith('UpperArm'):angle=abs(angle)
        elif name.endswith('Forearm') or any(f in name for f in ('IndexF','MiddleF','RingF','PinkyF')):angle=abs(angle)
    else:
        index = next(i for i,d in enumerate(degrees) if d)
        axis = Vector(tuple(1 if i==index else 0 for i in range(3)))
        angle = degrees[index]
    transform = Matrix.Translation(head) @ Matrix.Rotation(math.radians(angle),4,axis.normalized()) @ Matrix.Translation(-head)
    bone.matrix = armature.matrix_world.inverted() @ transform @ armature.matrix_world @ bone.matrix
    bpy.context.view_layer.update()


def positions(objects):
    graph = bpy.context.evaluated_depsgraph_get()
    blocks = []
    for obj in objects:
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            blocks.append(np.array([tuple(evaluated.matrix_world @ v.co) for v in mesh.vertices]))
        finally:
            evaluated.to_mesh_clear()
    return np.concatenate(blocks)


def run(objects, armature, directory):
    directory = Path(directory)
    rest = positions(objects)
    height = max(float(np.ptp(rest[:, 2])), .001)
    tolerance = height*1e-5
    clusters = {}
    for index, point in enumerate(rest):
        clusters.setdefault(tuple(np.rint(point/tolerance).astype(int)), []).append(index)
    pairs = [(group[0], i) for group in clusters.values() for i in group[1:]
             if np.linalg.norm(rest[group[0]]-rest[i]) <= tolerance]
    edges = []
    vertices = []
    offset = 0
    for obj in objects:
        vertices.extend({'object':obj.name,'index':v.index,'weights':{obj.vertex_groups[g.group].name:g.weight for g in v.groups if g.weight>0}} for v in obj.data.vertices)
        edges.extend((edge.vertices[0]+offset,edge.vertices[1]+offset) for edge in obj.data.edges)
        offset += len(obj.data.vertices)
    edges = np.asarray(edges,dtype=np.int64).reshape((-1,2))
    lengths = np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1)
    meaningful = lengths > height*1e-5
    poses = {'rest': []}
    for side, sign in [('L', -1), ('R', 1)]:
        for angle in (30, 60, 90):
            poses[f'{side}_arm_{angle}'] = [(side+'_UpperArm', (0,0,sign*angle))]
        poses[f'{side}_elbow'] = [(side+'_Forearm', (0,0,sign*85))]
        poses[f'{side}_step'] = [(side+'_Thigh', (35,0,0)), (side+'_Shin',(-50,0,0))]
        poses[f'{side}_fingers'] = [(side+'_'+finger+str(segment),(0,0,sign*30))
            for finger in ('IndexF','MiddleF','RingF','PinkyF') for segment in (1,2,3)]
    for axis in range(3):
        for sign in (-1,1):
            rotation = [0,0,0];rotation[axis]=sign*30
            poses[f'head_{axis}_{sign}']=[('Head',rotation)]
    saved = {bone.name:bone.matrix_basis.copy() for bone in armature.pose.bones}
    saved_modes = {bone.name:bone.rotation_mode for bone in armature.pose.bones}
    scene = bpy.context.scene
    camera = scene.camera
    camera_matrix = camera.matrix_world.copy() if camera else None
    old_path = scene.render.filepath
    if camera:
        center = Vector(tuple((rest.min(axis=0)+rest.max(axis=0))*.5))
        camera.location = center + Vector((0,-height*2.5,height*.12))
        camera.rotation_euler = (center-camera.location).to_track_quat('-Z','Y').to_euler()
    results = []
    try:
        for name, rotations in poses.items():
            for bone in armature.pose.bones:
                bone.matrix_basis = saved[bone.name]
            bpy.context.view_layer.update()
            for bone_name, degrees in rotations:
                bone = armature.pose.bones.get(bone_name)
                if bone is None:
                    raise RuntimeError('Motion audit missing bone: '+bone_name)
                swing(armature,bone_name,degrees)
            bpy.context.view_layer.update()
            posed = positions(objects)
            if posed.shape != rest.shape or not np.isfinite(posed).all():
                raise RuntimeError('Motion audit invalid geometry: '+name)
            gap = max((float(np.linalg.norm(posed[a]-posed[b])) for a,b in pairs), default=0)
            posed_lengths = np.linalg.norm(posed[edges[:,0]]-posed[edges[:,1]],axis=1)
            stretch = float(np.max(posed_lengths[meaningful]/lengths[meaningful],initial=1))
            ratios = np.divide(posed_lengths,lengths,out=np.ones_like(lengths),where=meaningful)
            worst = int(np.argmax(ratios)) if len(ratios) else None
            entry = {'pose':name,'max_seam_gap':gap,'tolerance':tolerance*4,
                     'max_edge_stretch':stretch,'stretch_limit':4,
                     'passed':gap<=tolerance*4 and stretch<=4}
            if worst is not None:
                entry['worst_edge'] = dict(vertices=edges[worst].tolist(),rest_length=float(lengths[worst]),
                    posed_length=float(posed_lengths[worst]),rest_midpoint=((rest[edges[worst,0]]+rest[edges[worst,1]])*.5).tolist())
                entry['worst_edge']['endpoints'] = [vertices[i] for i in edges[worst]]
            results.append(entry)
            if camera and name in {'L_arm_60','R_elbow','L_step','head_1_1'}:
                scene.render.filepath = str(directory/('motion_'+name+'.png'))
                bpy.ops.render.render(write_still=True)
                entry['textured_preview'] = scene.render.filepath
        report = {'passed':all(r['passed'] for r in results),'seam_pairs':len(pairs),
                  'poses':results,'scope':'synthetic pose seam continuity; not gameplay or collision verification'}
        (directory/'motion_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        if not report['passed']:
            raise RuntimeError('动作接缝检查未通过；未生成发布包，详见 motion_audit.json')
        return report
    finally:
        scene.render.filepath = old_path
        if camera_matrix is not None:
            camera.matrix_world = camera_matrix
        for bone in armature.pose.bones:
            bone.rotation_mode = saved_modes[bone.name]
            bone.matrix_basis = saved[bone.name]
        bpy.context.view_layer.update()

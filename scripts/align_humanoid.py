"""Pose an imported humanoid onto target joint landmarks, retaining source topology."""
import bpy
from mathutils import Matrix
from humanoid_bones import mapped_bones, select_source_bones


def synchronize_source_seams(meshes):
    groups = {}
    for obj in meshes:
        arm = next((m.object for m in obj.modifiers if m.type=='ARMATURE' and m.object),None)
        if not arm:continue
        for vertex in obj.data.vertices:
            point = obj.matrix_world @ vertex.co
            key = (arm.name,*(round(c,6) for c in point))
            groups.setdefault(key,[]).append((obj,vertex.index))
    count = 0
    for key,members in groups.items():
        if len(members)<2:continue
        deform_names = set(bpy.data.objects[key[0]].data.bones.keys())
        weights = {}
        for obj,index in members:
            for item in obj.data.vertices[index].groups:
                name = obj.vertex_groups[item.group].name
                if name not in deform_names:continue
                weights[name] = weights.get(name,0)+item.weight
        total = sum(weights.values())
        if total <= 0:continue
        for obj,index in members:
            for group in obj.vertex_groups:
                if group.name in deform_names:group.remove([index])
            for name,weight in weights.items():
                group = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
                group.add([index],weight/total,'REPLACE')
        count += 1
    return count


def align(arms, target, meshes):
    if not arms:
        raise ValueError('源模型没有人形骨架；当前支持带骨架的 PMX、PMD、FBX 和 Blender 模型')
    mapping = mapped_bones(arms,target,inherit=False)
    links = {'Hip':'Spine_1','Spine_0':'Spine_1','Spine_1':'Spine_2','Spine_2':'Neck_1','Neck_1':'Head'}
    for side in ('L','R'):
        for a,b in [('Shoulder','UpperArm'),('UpperArm','Forearm'),('Forearm','Hand'),('Hand','MiddleF1'),
                    ('Thigh','Shin'),('Shin','Foot'),('Foot','Toe')]:
            links[side+'_'+a] = side+'_'+b
        for finger in ('Thumb','IndexF','MiddleF','RingF','PinkyF'):
            for i in (1,2):links[f'{side}_{finger}{i}']=f'{side}_{finger}{i+1}'
    seam_count = synchronize_source_seams(meshes)
    adjusted = []
    for arm in arms:
        selected = {name:item[1] for name,item in select_source_bones([arm],target,meshes).items()}
        if not {'Head','L_UpperArm','R_UpperArm','L_Hand','R_Hand'} <= set(selected):
            raise ValueError('源文件不是已识别的完整人形骨架；未更改原始文件')
        # Imported IK solvers would otherwise overwrite direct deform-bone edits.
        for bone in arm.pose.bones:
            for constraint in bone.constraints:constraint.mute=True
        bpy.context.view_layer.update()
        inverse = arm.matrix_world.inverted()
        ordered = sorted(selected.items(),key=lambda item:len(item[1].parent_recursive))
        for name,bone in ordered:
            # Preserve the source's torso proportions. Only the limb pose is retargeted.
            if not name.startswith(('L_','R_')) or name.endswith('_Shoulder'):
                continue
            target_bone = target.data.bones.get(name)
            if not target_bone:continue
            current_head = arm.matrix_world @ bone.head
            target_head = target.matrix_world @ target_bone.head_local
            next_name = links.get(name)
            transform = Matrix.Identity(4)
            if next_name in selected and target.data.bones.get(next_name):
                current_delta = arm.matrix_world @ selected[next_name].head-current_head
                target_delta = target.matrix_world @ target.data.bones[next_name].head_local-target_head
                if current_delta.length > 1e-6 and target_delta.length > 1e-6:
                    # Keep bone scales uniform: inherited nonuniform stretch shears finger chains.
                    # Child landmark translations provide the length adjustment through skinning.
                    transform = current_delta.rotation_difference(target_delta).to_matrix().to_4x4()
            bone.matrix = inverse @ Matrix.Translation(target_head) @ transform @ Matrix.Translation(-current_head) @ arm.matrix_world @ bone.matrix
            bpy.context.view_layer.update()
            adjusted.append(name)
    return dict(method='semantic_joint_landmarks',bones=adjusted,synchronized_seams=seam_count)

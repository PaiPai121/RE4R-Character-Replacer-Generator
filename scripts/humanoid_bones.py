"""Shared source bone semantics for pose guides and export binding."""
def bone_aliases():
    result = {'頭':'Head', '首':'Neck_1', '上半身':'Spine_1', '上半身2':'Spine_2',
              '下半身':'Hip', 'センター':'Hip', 'head':'Head', 'neck':'Neck_1', 'hips':'Hip',
              'spine':'Spine_0', 'chest':'Spine_1', 'upperchest':'Spine_2'}
    for jp, side in [('左','L'),('右','R')]:
        for key, value in {'肩':'Shoulder','腕':'UpperArm','ひじ':'Forearm','手首':'Hand',
                           '足':'Thigh','ひざ':'Shin','足首':'Foot','つま先':'Toe'}.items():
            result[jp+key] = side+'_'+value
        for key,value in {'足D':'Thigh','ひざD':'Shin','足首D':'Foot','足先EX':'Toe'}.items():
            result[jp+key] = side+'_'+value
        for finger, target in [('親指','Thumb'),('人指','IndexF'),('中指','MiddleF'),('薬指','RingF'),('小指','PinkyF')]:
            for i in range(3):
                digit = i if finger == '親指' else i+1
                for num in (str(digit), '０１２３'[digit]):
                    result[jp+finger+num] = f'{side}_{target}{i+1}'
        english = 'left' if side == 'L' else 'right'
        for key,value in {'shoulder':'Shoulder','arm':'UpperArm','upperarm':'UpperArm',
                          'forearm':'Forearm','lowerarm':'Forearm','hand':'Hand',
                          'upleg':'Thigh','upperleg':'Thigh','leg':'Shin','lowerleg':'Shin','foot':'Foot','toebase':'Toe'}.items():
            result[english+key] = side+'_'+value
        for finger, target_finger in [('thumb','Thumb'),('index','IndexF'),('middle','MiddleF'),('ring','RingF'),('pinky','PinkyF')]:
            for segment in (1,2,3):
                result[english+'hand'+finger+str(segment)] = f'{side}_{target_finger}{segment}'
                result[english+finger+str(segment)] = f'{side}_{target_finger}{segment}'
    return result


def select_source_bones(arms,target,meshes):
    mapping = mapped_bones(arms,target,inherit=False)
    weights = {}
    for obj in meshes:
        for vertex in obj.data.vertices:
            for item in vertex.groups:
                name = obj.vertex_groups[item.group].name
                weights[name] = weights.get(name,0)+item.weight
    selected = {}
    for arm in arms:
        for bone in arm.pose.bones:
            name = mapping.get(bone.name)
            if name and (name not in selected or weights.get(bone.name,0)>weights.get(selected[name][1].name,0)):
                selected[name] = (arm,bone)
    return selected


def mapped_bones(source_arms, target, inherit=True):
    aliases = bone_aliases()
    names = set(target.data.bones.keys())
    result = {n:n for n in names}
    def direct(bone, arm):
        labels = [bone.name, bone.name.split(':')[-1]]
        metadata = getattr(arm.pose.bones.get(bone.name), 'mmd_bone', None)
        if metadata:
            labels += [metadata.name_j, metadata.name_e]
        for label in labels:
            normalized = label.replace('_','').replace(' ','').lower()
            name = label if label in names else aliases.get(label, aliases.get(normalized))
            if name in names:
                return name
        return None
    for arm in source_arms:
        for bone in arm.data.bones:
            current = bone
            while current:
                name = direct(current, arm)
                if name:
                    result[bone.name] = name
                    break
                current = current.parent if inherit else None
    return result

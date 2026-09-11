"""Profile-driven RE4 prototype, isolated from the Kafka versioned builders."""
import copy
import importlib
import json
import math
import re
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import create_pose_alignment_workspace as pose


from humanoid_bones import mapped_bones


def texture_nodes(tree, seen=None):
    seen = set() if seen is None else seen
    if not tree or tree in seen:
        return []
    seen.add(tree)
    images = []
    for node in tree.nodes:
        if node.type == 'TEX_IMAGE':
            images.append(node)
        elif node.type == 'GROUP':
            images.extend(texture_nodes(node.node_tree, seen))
    return images


def _socket(sockets, *names):
    return next((socket for socket in sockets if socket.name in names), None)


def _images_from_output(node, output_socket, seen=None):
    """Return image nodes feeding one shader output, including nested node groups."""
    seen = set() if seen is None else seen
    key = (node.as_pointer(), output_socket.identifier)
    if key in seen:
        return []
    seen.add(key)
    if node.type == 'TEX_IMAGE':
        return [node] if node.image else []
    if node.type == 'GROUP' and node.node_tree:
        index = list(node.outputs).index(output_socket)
        found = []
        for group_output in (item for item in node.node_tree.nodes if item.type == 'GROUP_OUTPUT'):
            internal = next((item for item in group_output.inputs
                             if item.identifier == output_socket.identifier), None)
            if internal is None and index < len(group_output.inputs):
                internal = group_output.inputs[index]
            if internal is not None:
                found.extend(_images_from_input(internal, seen))
        return found
    found = []
    for input_socket in node.inputs:
        found.extend(_images_from_input(input_socket, seen))
    return found


def _images_from_input(input_socket, seen=None):
    found = []
    for link in input_socket.links:
        found.extend(_images_from_output(link.from_node, link.from_socket, seen))
    return found


def _unique_image_nodes(nodes):
    result = []
    seen = set()
    for node in nodes:
        if not node.image:
            continue
        key = node.image.as_pointer()
        if key not in seen:
            seen.add(key)
            result.append(node)
    return result


def _base_color_score(node):
    image = node.image
    path_name = Path(image.filepath.replace('\\', '/')).name if image.filepath else ''
    stem = Path(path_name or image.name).stem.lower()
    node_text = f'{node.name} {node.label}'.lower()
    tokens = set(filter(None, re.split(r'[^a-z0-9]+', stem)))
    score = 0
    positive = {'albedo', 'basecolor', 'base', 'diffuse', 'diff', 'color', 'colour'}
    negative = {
        'alpha', 'ao', 'bump', 'cavity', 'csar', 'emit', 'emission', 'emissive',
        'height', 'mask', 'metal', 'metallic', 'mra', 'n', 'normal', 'nrm', 'opacity',
        'orm', 'rma', 'rough', 'roughness', 'spec', 'specular', 'sss', 'thickness',
    }
    if tokens & positive or re.search(r'(?:^|[_ .-])(base_?color|albd|albedo|diffuse|diff)(?:$|[_ .-])', stem):
        score += 120
    if re.search(r'(?:^|[_ .-])[cd](?:$|[_ .-])', stem):
        score += 100
    if tokens & negative:
        score -= 240
    if any(word in node_text for word in ('base color', 'albedo', 'diffuse')):
        score += 40
    color_space = getattr(getattr(image, 'colorspace_settings', None), 'name', '')
    if color_space == 'sRGB':
        score += 10
    elif color_space and color_space != 'sRGB':
        score -= 5
    return score


def _choose_base_image(material, nodes, context):
    nodes = _unique_image_nodes(nodes)
    if not nodes:
        return None
    if len(nodes) == 1:
        return nodes[0].image
    ranked = sorted(((_base_color_score(node), node) for node in nodes),
                    key=lambda item: item[0], reverse=True)
    best_score, best = ranked[0]
    second_score = ranked[1][0]
    if best_score > 0 and best_score >= second_score + 40:
        return best.image
    candidates = ', '.join(
        f'{Path(node.image.filepath or node.image.name).name} ({score:+d})'
        for score, node in ranked)
    raise ValueError(
        f'材质 {material.name} 的基础颜色贴图存在歧义（{context}）：{candidates}。'
        '请把正确贴图连到 Principled BSDF 的 Base Color，或使用 _C/Albedo/Diffuse 后缀。'
    )


def base_image(material):
    if not material or not material.node_tree:
        raise ValueError('模型缺少可转换的材质节点')
    all_nodes = texture_nodes(material.node_tree)
    mmd_nodes = [node for node in all_nodes if node.name == 'mmd_base_tex' and node.image]
    if mmd_nodes:
        return mmd_nodes[0].image

    principled = next((node for node in material.node_tree.nodes
                       if node.type == 'BSDF_PRINCIPLED'), None)
    base_socket = _socket(principled.inputs, 'Base Color') if principled else None
    if base_socket and base_socket.links:
        linked = _choose_base_image(material, _images_from_input(base_socket), '基础颜色连线')
        if linked:
            return linked

    candidate = _choose_base_image(material, all_nodes, '材质节点树')
    if candidate:
        return candidate

    if principled and base_socket and not base_socket.links:
        image = bpy.data.images.new('BaseColor_'+material.name,width=4,height=4,alpha=True)
        color = list(base_socket.default_value)
        # Shader constants are linear; the packaged base-color texture is sRGB.
        color[:3] = [12.92*c if c <= .0031308 else 1.055*c**(1/2.4)-.055 for c in color[:3]]
        alpha = _socket(principled.inputs, 'Alpha')
        color[3] = alpha.default_value if alpha else 1.0
        image.pixels[:] = color*16
        return image
    raise ValueError(f'材质 {material.name} 的基础颜色无法自动解析，未生成发布包')


def recover_missing_images(images, search_roots):
    """Repair stale absolute image paths, but only when the basename is unambiguous."""
    roots = []
    for root in search_roots:
        root = Path(root).resolve()
        if root.is_dir() and root not in roots:
            roots.append(root)
    recovered = []
    for image in images:
        if image.source != 'FILE' or image.packed_file or image.has_data or not image.filepath:
            continue
        current = Path(bpy.path.abspath(image.filepath))
        if current.is_file():
            continue
        basename = Path(image.filepath.replace('\\', '/')).name
        if not basename:
            continue
        matches = []
        for root in roots:
            matches.extend(path for path in root.rglob('*')
                           if path.is_file() and path.name.lower() == basename.lower())
        matches = sorted(set(path.resolve() for path in matches))
        if len(matches) == 1:
            image.filepath = str(matches[0])
            recovered.append((image.name, str(matches[0])))
        elif len(matches) > 1:
            print(f'贴图 {image.name} 存在多个同名候选，不自动选择：' + ' | '.join(map(str, matches)))
    return recovered


def main(config):
    work = Path(config['work']); package = work / 'package'
    profile = config['profile']
    # This is a shader/slot compatibility preset, not source character geometry.
    preset = (ROOT / 'replacer_app/presets' / ('re4_'+profile['id'])).resolve()
    preset.relative_to((ROOT/'replacer_app/presets').resolve())
    if not (preset / 'profile.json').is_file():
        raise RuntimeError('缺少游戏材质与资源槽预设')
    policy = json.loads((preset / 'profile.json').read_text())
    if profile['id'] != policy['character']:
        raise RuntimeError('目标角色尚未建立材质与资源槽兼容预设')
    addon = pose.register_local_package('re_mesh_builder', ROOT / 'tools/RE-Mesh-Editor')
    sys.path.insert(0, pose.DEFAULT_MMD_TOOLS_PARENT)
    import mmd_tools
    mmd_tools.register()
    bpy.ops.wm.open_mainfile(filepath=config['input'])
    # Snapshot relocation must not rebase external textures onto the job folder.
    for image in bpy.data.images:
        if image.filepath.startswith('//'):
            image.filepath = bpy.path.abspath(image.filepath, start=str(Path(config['originalBlend']).parent))
    recovered = recover_missing_images(
        bpy.data.images,
        (Path(config['sourceModel']).parent, Path(config['originalBlend']).parent),
    )
    for image_name, path in recovered:
        print(f'已恢复贴图路径：{image_name} -> {path}')
    target = next((o for o in bpy.data.objects if o.type=='ARMATURE' and 'REFERENCE_ARMATURE' in o.name), None)
    sources = [o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('SOURCE_MODEL__')]
    if not target or not sources:
        raise RuntimeError('保存的姿势工作区缺少源模型或目标骨架')
    source_arms = [o for o in bpy.data.objects if o.type=='ARMATURE' and o != target]
    mapping = mapped_bones(source_arms, target)
    mapped_source = {mapping.get(b.name) for arm in source_arms for b in arm.data.bones}
    required = {side+'_'+part for side in ('L','R') for part in ('UpperArm','Forearm','Hand','Thigh','Shin','Foot')}
    if required - mapped_source:
        raise ValueError('缺少四肢骨骼映射：'+', '.join(sorted(required-mapped_source)))
    graph = bpy.context.evaluated_depsgraph_get()
    baked = []
    weighted_bones = set()
    for source in sources:
        weights = []
        for v in source.data.vertices:
            row = {}
            for g in v.groups:
                name = mapping.get(source.vertex_groups[g.group].name)
                if name:
                    row[name] = row.get(name,0)+g.weight
            total = sum(row.values())
            if total < .99:
                raise ValueError(f'{source.name} 顶点 {v.index} 的骨骼映射不完整；现场已保留')
            weights.append({n:w/total for n,w in row.items()})
            weighted_bones.update(n for n,w in row.items() if w>1e-6)
        evaluated = source.evaluated_get(graph)
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=graph)
        if len(mesh.vertices) != len(weights):
            raise ValueError('修改器改变了顶点数量，无法可靠对应蒙皮')
        mesh.transform(source.matrix_world)
        obj = bpy.data.objects.new('BoundCharacter',mesh);bpy.context.scene.collection.objects.link(obj)
        for name in target.data.bones.keys():
            obj.vertex_groups.new(name=name)
        for group in obj.vertex_groups:
            group.remove(list(range(len(mesh.vertices))))
        for i,row in enumerate(weights):
            top = sorted(row.items(), key=lambda v:v[1], reverse=True)[:8]
            total = sum(w for n,w in top)
            for n,w in top:
                obj.vertex_groups[n].add([i], w/total, 'REPLACE')
        mod = obj.modifiers.new('Target armature','ARMATURE');mod.object=target
        baked.append(obj)
    coverage = set()
    for name in weighted_bones:
        bone = target.data.bones.get(name)
        while bone:
            coverage.add(bone.name);bone=bone.parent
    if required-coverage:
        raise ValueError('骨架名称已映射但对应肢体没有蒙皮：'+', '.join(sorted(required-coverage)))
    keep = set(baked+[target])
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    # A shared rest-space seam must use one weight vector across material splits.
    seams = {}
    for obj in baked:
        for v in obj.data.vertices:
            k = tuple(round(x,6) for x in v.co)
            seams.setdefault(k,[]).append((obj,v.index))
    for group in seams.values():
        if len(group)<2:continue
        values={}
        for obj,i in group:
            for g in obj.data.vertices[i].groups:
                n=obj.vertex_groups[g.group].name;values[n]=values.get(n,0)+g.weight
        values=dict(sorted(values.items(),key=lambda v:v[1],reverse=True)[:8]);total=sum(values.values())
        for obj,i in group:
            for g in obj.vertex_groups:g.remove([i])
            for n,w in values.items():obj.vertex_groups[n].add([i],w/total,'REPLACE')
    from regularize_skin_weights import regularize
    skin_regularization = regularize(baked,target)
    (work/'skin_regularization.json').write_text(json.dumps(skin_regularization,indent=2))
    material_map={}
    parts=[]
    for obj in baked:
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        before=set(bpy.data.objects)
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.separate(type='MATERIAL');bpy.ops.object.mode_set(mode='OBJECT')
        parts += [obj]+[o for o in set(bpy.data.objects)-before if o.type=='MESH']
    collection=bpy.data.collections.new('character.mesh');bpy.context.scene.collection.children.link(collection)
    for obj in parts+[target]:
        for c in list(obj.users_collection):c.objects.unlink(obj)
        collection.objects.link(obj)
    for i,obj in enumerate(parts):
        mat=obj.data.materials[0] if obj.data.materials else None
        if not mat:raise ValueError('源模型存在无材质网格')
        if mat not in material_map:material_map[mat]=f'Material_{len(material_map):03d}'
        obj.name=f'Group_0_Sub_{i}__{material_map[mat]}'
        for p in obj.data.polygons:p.use_smooth=True
        if not obj.data.uv_layers:raise ValueError('源模型缺少 UV')
        if len(obj.data.uv_layers)<2:obj.data.uv_layers.new(name='UV2',do_init=True)
        color=obj.data.color_attributes.get('Color') or obj.data.color_attributes.new(name='Color',type='BYTE_COLOR',domain='CORNER')
        for v in color.data:v.color=(1,1,1,1)
    bpy.ops.wm.save_as_mainfile(filepath=str(work/'bound.blend'))
    meshpath=work/'character.mesh.221108797'
    options=dict(targetCollection=collection.name, exportAllLODs=False, exportBlendShapes=False,rotate90=True,
                 autoSolveRepeatedUVs=True,preserveSharpEdges=True,useBlenderMaterialName=False,
                 preserveBoneMatrices=False,exportBoundingBoxes=False,selectedOnly=False)
    if not addon.exportREMeshFile(str(meshpath),options):raise RuntimeError('模型导出失败')
    parser=importlib.import_module(addon.__name__+'.modules.mdf.file_re_mdf')
    mdf=parser.readMDF(str(preset/'neutral.mdf2.32'))
    template=mdf.materialList[0];mdf.materialList=[]
    texutil=importlib.import_module(addon.__name__+'.modules.tex.re_tex_utils')
    texconvert=importlib.import_module(addon.__name__+'.modules.tex.blender_re_tex')
    textures=work/'textures';textures.mkdir()
    inputs=[]; image_paths={}; converted_images={}
    for mat,name in material_map.items():
        img=base_image(mat)
        if img in converted_images:
            image_paths[name] = converted_images[img]
            continue
        if img and not img.has_data:
            img.reload()
            _ = img.pixels[0] if len(img.pixels) else None
        if not img or not img.has_data:raise ValueError(f'{mat.name} 贴图丢失')
        path=textures/(name+'_ALBD.tga')
        original_path, original_format=img.filepath_raw,img.file_format
        img.filepath_raw=str(path);img.file_format='TARGA';img.save()
        img.filepath_raw=original_path;img.file_format=original_format
        inputs.append((str(path),'BC7_UNORM_SRGB'));image_paths[name]=path
        converted_images[img]=path
    texutil.ImageListToDDS(inputs,outDir=str(textures),generateMipMaps=True)
    from dds_fallback import write_rgba8_dds
    for path in set(image_paths.values()):
        if not path.with_suffix('.dds').is_file():
            write_rgba8_dds(path, path.with_suffix('.dds'))
    names=sorted({p.stem+'.dds' for p in image_paths.values()})
    if any(not (textures/n).is_file() for n in names):raise RuntimeError('DDS 转换未完成')
    success,failed=texconvert.convertTexDDSList(fileNameList=names,inDir=str(textures),outDir=str(textures),gameName='RE4',createStreamingTex=False,texToPNG=False)
    if failed or success!=len(names):raise RuntimeError('TEX 转换失败')
    for path in set(image_paths.values()):
        if (textures/(path.stem+'.tex.143221013')).stat().st_size <= 128:
            raise RuntimeError('TEX 文件没有有效的像素数据')
    texture_root=f'_Chainsaw/Character/ch/Replacer/{work.name}'
    for name,path in image_paths.items():
        material=copy.deepcopy(template);material.materialName=name
        binding=f'{texture_root}/{path.stem}.tex'
        for tex in material.textureList:
            if tex.textureType=='BaseDielectricMap':tex.texturePath=binding
        mdf.materialList.append(material)
        dest=package/'natives/stm'/(binding+'.143221013');dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(textures/(path.stem+'.tex.143221013'),dest)
    for name in policy['alias_materials']:
        material=copy.deepcopy(mdf.materialList[0]);material.materialName=name;mdf.materialList.append(material)
    from material_contract import write_for_mesh, slot_pairs
    mesh_parser=importlib.import_module(addon.__name__+'.modules.mesh.file_re_mesh')
    mdfpath=work/'character.mdf2.32'
    write_for_mesh(mdf,meshpath,mdfpath,mesh_parser,parser)
    for rel in policy['body_meshes']:
        dest=package/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(meshpath,dest)
    for rel in policy['partial_meshes']:
        dest=package/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(preset/'partials'/rel,dest)
    for slot_mesh, slot_mdf in slot_pairs(package,policy):
        write_for_mesh(mdf,slot_mesh,slot_mdf,mesh_parser,parser)
    validation = dict(config, validate_only=True, material_names=list(material_map.values()))
    (work/'validation_request.json').write_text(json.dumps(validation,ensure_ascii=False),encoding='utf-8')


def validate_export(config):
    work = Path(config['work']); package = work/'package'
    profile = config['profile']
    meshpath = work/'character.mesh.221108797'
    mdfpath = work/'character.mdf2.32'
    addon = pose.register_local_package('re_mesh_validation',ROOT/'tools/RE-Mesh-Editor')
    parser = importlib.import_module(addon.__name__+'.modules.mdf.file_re_mdf')
    from material_contract import mesh_names, require_names, validate_package
    mesh_parser=importlib.import_module(addon.__name__+'.modules.mesh.file_re_mesh')
    policy=json.loads((ROOT/'replacer_app/presets'/('re4_'+profile['id'])/'profile.json').read_text())
    require_names(mesh_names(meshpath,mesh_parser),
                  [m.materialName for m in parser.readMDF(str(mdfpath)).materialList])
    material_contracts=validate_package(package,policy,mesh_parser,parser)
    # Validate the on-disk export, not merely the Blender workspace.
    for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material, do_unlink=True)
    options=dict(clearScene=True,createCollections=True,loadMaterials=False,loadMDFData=False,
                 importAllLODs=False,importBlendShapes=False,rotate90=True,mergeArmature='',importArmatureOnly=False,
                 mergeGroups=False,importShadowMeshes=False,importOcclusionMeshes=False,importBoundingBoxes=False,
                 loadShellFur=False,loadUnusedTextures=False,loadUnusedProps=False,useBackfaceCulling=False,
                 reloadCachedTextures=False,mdfPath='')
    addon.importREMeshFile(str(meshpath),options)
    exported=[o for o in bpy.data.objects if o.type=='MESH'];arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
    if not exported:raise RuntimeError('回灌模型为空')
    for obj in exported:
        for v in obj.data.vertices:
            if not all(math.isfinite(x) for x in v.co) or abs(sum(g.weight for g in v.groups)-1)>.02:
                raise RuntimeError('回灌模型存在无效顶点或权重')
    # Load the exported material package for the proof render.
    entry=bpy.context.preferences.addons.new();entry.module=addon.__name__
    entry.preferences.textureCachePath=str(work/'cache');entry.preferences.useDDS=True;entry.preferences.saveChunkPaths=False
    chunk=entry.preferences.chunkPathList_items.add();chunk.gameName='RE4'
    chunk.path=str(ROOT/'work/game_resources/reference/natives/stm')
    importer=importlib.import_module(addon.__name__+'.modules.mdf.blender_re_mesh_mdf')
    mats={m.name:m for o in exported for m in o.data.materials if m}
    if set(mats) != set(config['material_names']):
        raise RuntimeError('回灌材质名称与导出清单不一致：'+repr(sorted(mats)))
    importer.importMDF(parser.readMDF(str(mdfpath)),mats,False,False,True,True,chunkPath=str(package/'natives/stm'),gameName='RE4',arrangeNodes=False)
    for mat in mats.values():
        images = texture_nodes(mat.node_tree)
        for node in images:
            if node.image and not node.image.has_data:
                _ = node.image.pixels[0] if len(node.image.pixels) else None
        if not images or any(not n.image or not n.image.has_data for n in images):
            raise RuntimeError('回灌材质缺少贴图')
    arm.name='REFERENCE_ARMATURE'
    from character_motion_audit import run as audit_motion
    proof=pose.setup_preview_camera(exported,exported,work,'exported')
    motion_report = audit_motion(exported, arm, work)
    shutil.copy2(proof['front'],package/'preview.png')
    title=Path(config['sourceModel']).stem.replace('\n',' ').replace('\r',' ')
    (package/'modinfo.ini').write_text(f'name={title} - {profile["label"]}\nversion=0.2.0-preview\ndescription=Automatic character replacement. Experimental build.\nauthor=Character Replacer\nscreenshot=preview.png\n',encoding='utf-8')
    bpy.ops.wm.save_as_mainfile(filepath=str(work/'roundtrip.blend'))
    (work/'result.json').write_text(json.dumps(dict(passed=True,source_sha256=config['source_sha256'],mesh=str(meshpath),
        previewImages=proof,motionAudit=motion_report,materialContracts=material_contracts,validation='mesh/material contracts, textured roundtrip and synthetic pose seams',experimental=True,
        limitations=['Synthetic seam tests do not verify gameplay, collisions or arbitrary open boundaries.','Only mapped armatures and supported base-color materials are accepted.'])))


if __name__=='__main__':
    request = json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8'))
    try:
        validate_export(request) if request.get('validate_only') else main(request)
    except Exception as exc:
        (Path(request['work'])/'failure.json').write_text(json.dumps({'error':str(exc)}, ensure_ascii=False), encoding='utf-8')
        raise

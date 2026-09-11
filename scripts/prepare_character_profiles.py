"""Build compatibility data from discovered game slots, without source artwork."""
import copy
import importlib
import json
import shutil
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'replacer_app'))
import create_pose_alignment_workspace as pose
import game_resources as resources


NEUTRAL_TEXTURES = {
    'BaseDielectricMap': 'systems/rendering/NullWhite.tex',
    'NormalRoughnessMap': 'systems/rendering/NullNormalRoughness.tex',
    'AlphaTranslucentOcclusionCavityMap': 'systems/rendering/NullWhite.tex',
    'MaskMap': 'systems/rendering/NullWhite.tex',
    'DetailMap': '_Chainsaw/MasterMaterial/Textures/NullGrayArray.tex',
    'MicroDetailDetailMap': '_Chainsaw/MasterMaterial/Textures/NullGrayArray.tex',
    'WrinkleNormalMap': 'systems/rendering/NullNormal.tex',
    'Wind_MaskMap': 'systems/rendering/NullWhite.tex',
    'Noise3D': '_Chainsaw/MasterMaterial/Textures/Noise3D_01_MSK3.tex',
    'RecordSys_rtt': '_Chainsaw/VFX/RecordSystem/RecordTexture/BaseTextures/null_black_MSK4.tex',
    'RecordSys_Fix': '_Chainsaw/VFX/RecordSystem/RecordTexture/BaseTextures/null_black_MSK4.tex',
    'RecordSys_Protect': '_Chainsaw/VFX/RecordSystem/RecordTexture/BaseTextures/null_black_MSK4.tex',
    'BloodMask': 'systems/rendering/NullBlack.tex',
    'BloodFlow_rtt': 'systems/rendering/NullBlack.tex',
    'BloodFlow_uv': 'systems/rendering/NullBlack.tex',
    'Injury_Map_ALBA': 'systems/rendering/NullBlack.tex',
    'Injury_Map_NRM': 'systems/rendering/NullNormal.tex',
    'Stain_Cloth_Map_MSK4': 'systems/rendering/NullBlack.tex',
    'clothDamagemaskMap': 'systems/rendering/NullWhite.tex',
    'DirtMask_Atex': 'systems/rendering/NullBlack.tex',
    'Rec_Rain_WaterRiple': 'RE_ENGINE_LIBRARY/VFX_Library/Texture/TEX_Vector/tex_capcom_vector_water_0011_Array_NRMR.tex',
    'Rec_Rain_WetMask': 'systems/rendering/NullWhite.tex',
}


def write_neutral_mdf(parser, source_path, destination):
    source = parser.readMDF(str(source_path))
    material = next((m for m in source.materialList
                     if any(t.textureType == 'BaseDielectricMap' for t in m.textureList)), None)
    if material is None:
        raise RuntimeError(f'No base-color material in {source_path}')
    material = copy.deepcopy(material)
    material.materialName = 'NeutralCharacter'
    for texture in material.textureList:
        texture.texturePath = NEUTRAL_TEXTURES.get(texture.textureType,
                                                   'systems/rendering/NullWhite.tex')
    source.materialList = [material]
    # RE Mesh Editor seeks to GPUBufferOffset even when a material has no GPBF
    # entries. Rebase that legacy source offset to the new one-material string table.
    size = parser.SIZEDATA(32)
    material.GPUBufferOffset = (size.HEADER_SIZE + size.MATERIAL_ENTRY_SIZE +
                                len(material.textureList) * size.TEXTURE_ENTRY_SIZE +
                                len(material.propertyList) * size.PROPERTY_ENTRY_SIZE)
    parser.writeMDF(source, str(destination))
    check = parser.readMDF(str(destination))
    if [m.materialName for m in check.materialList] != ['NeutralCharacter']:
        raise RuntimeError('Neutral material roundtrip failed')


def prepare():
    data = resources.read_index()
    if not data:
        raise RuntimeError('Run a game resource scan first')
    reference = resources.CACHE/'reference'
    resources.extract(data,list(data['resources']),reference)
    addon = pose.register_local_package('profile_mesh_editor',ROOT/'tools/RE-Mesh-Editor')
    parser = importlib.import_module(addon.__name__+'.modules.mdf.file_re_mdf')
    prepared = []
    for character in resources.CHARACTERS:
        ids = character['characterIds']
        paths = [p for p in data['resources'] if any('/'+i+'/' in p for i in ids)]
        body = [p for p in paths if '/00/' in p and '.mesh.' in p]
        primary = next((p for p in body if p.endswith(character['primaryTarget']+'_00.mesh.221108797')),None)
        if not primary:
            continue
        folder = ROOT/'replacer_app/presets'/('re4_'+character['id'])
        folder.mkdir(parents=True,exist_ok=True)
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj,do_unlink=True)
        opts = dict(clearScene=True,createCollections=True,loadMaterials=False,loadMDFData=False,
                    loadShellFur=False,loadUnusedTextures=False,loadUnusedProps=False,useBackfaceCulling=False,
                    reloadCachedTextures=False,mdfPath='',importAllLODs=False,importBlendShapes=False,
                    rotate90=True,mergeArmature='',importArmatureOnly=False,mergeGroups=False,
                    importShadowMeshes=False,importOcclusionMeshes=False,importBoundingBoxes=False)
        addon.importREMeshFile(str(reference/primary),opts)
        arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
        required = {s+'_'+p for s in ('L','R') for p in ('UpperArm','Forearm','Hand','Thigh','Shin','Foot')}
        if required-set(arm.data.bones.keys()):
            continue
        bone_names = list(arm.data.bones.keys())
        for obj in list(bpy.data.objects):
            if obj != arm:
                bpy.data.objects.remove(obj,do_unlink=True)
        collection = bpy.data.collections.new('hidden.mesh')
        bpy.context.scene.collection.children.link(collection)
        for c in list(arm.users_collection):c.objects.unlink(arm)
        collection.objects.link(arm)
        mesh = bpy.data.meshes.new('HiddenReplacement')
        mesh.from_pydata([(0,0,0),(0.000001,0,0),(0,0.000001,0)],[],[(0,1,2)])
        obj = bpy.data.objects.new('Group_0_Sub_0__NeutralHidden',mesh)
        collection.objects.link(obj)
        mesh.materials.append(bpy.data.materials.new('NeutralHidden'))
        mesh.uv_layers.new(name='UVMap');mesh.uv_layers.new(name='UV2')
        color = mesh.color_attributes.new(name='Color',type='BYTE_COLOR',domain='CORNER')
        for value in color.data:value.color=(1,1,1,1)
        group = obj.vertex_groups.new(name='Hip');group.add([0,1,2],1,'REPLACE')
        modifier = obj.modifiers.new('Skeleton','ARMATURE');modifier.object=arm
        hidden = folder/'hidden.mesh.221108797'
        opts = dict(targetCollection=collection.name,exportAllLODs=False,exportBlendShapes=False,rotate90=True,
                    autoSolveRepeatedUVs=True,preserveSharpEdges=True,useBlenderMaterialName=False,
                    preserveBoneMatrices=False,exportBoundingBoxes=False,selectedOnly=False)
        if not addon.exportREMeshFile(str(hidden),opts):raise RuntimeError('Hidden slot export failed')
        partials = [p for p in paths if '.mesh.' in p and p not in body]
        meshes = body + partials
        mesh_parents = {Path(p).parent.as_posix().lower() for p in meshes}
        mdf_files = [p for p in paths if '.mdf2.' in p and
                     Path(p).parent.as_posix().lower() in mesh_parents]
        for path in partials:
            dest = folder/'partials'/path;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(hidden,dest)
        primary_mdf = next((p for p in mdf_files
                            if Path(p).parent == Path(primary).parent and
                            Path(p).name == Path(primary).name.replace('.mesh.221108797', '.mdf2.32')),
                           next((p for p in mdf_files if Path(p).parent == Path(primary).parent), None))
        if primary_mdf is None:
            raise RuntimeError(f'No primary material file for {character["id"]}')
        write_neutral_mdf(parser, reference/primary_mdf, folder/'neutral.mdf2.32')
        policy = dict(character=character['id'],body_meshes=body,partial_meshes=partials,
                      mdf_files=mdf_files,alias_materials=['NeutralHidden'],
                      reference_mesh=str(reference/primary),bone_names=bone_names,
                      provenance='Scanned game PAK; generated hidden geometry; no source model geometry',
                      in_game_verified=False)
        (folder/'profile.json').write_text(json.dumps(policy,indent=2),encoding='utf-8')
        prepared.append(character['id'])
    print(json.dumps({'prepared':prepared}))


if __name__=='__main__':
    prepare()

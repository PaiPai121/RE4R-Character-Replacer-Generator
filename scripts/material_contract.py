"""Validate the actual on-disk mesh/material contract before Blender binding."""
import copy
from pathlib import Path


def mesh_names(path, mesh_parser):
    mesh = mesh_parser.readREMesh(str(path))
    return [mesh.rawNameList[i] for i in mesh.materialNameRemapList]


def require_names(expected, actual):
    if not expected or len(set(expected)) != len(expected) or expected != actual:
        raise ValueError(f'MESH/MDF material mismatch: expected {expected}, got {actual}')


def slot_pairs(package, policy):
    meshes = [Path(p) for p in policy['body_meshes'] + policy['partial_meshes']]
    for rel in policy['mdf_files']:
        material = Path(rel)
        candidates = [p for p in meshes if p.parent == material.parent]
        if len(candidates) > 1:
            material_stem = material.name.removesuffix('.mdf2.32')
            exact = [p for p in candidates
                     if p.name.removesuffix('.mesh.221108797') == material_stem]
            if len(exact) == 1:
                candidates = exact
        if len(candidates) != 1:
            raise ValueError(f'Ambiguous or missing mesh for {rel}: {candidates}')
        yield Path(package)/candidates[0], Path(package)/material


def write_for_mesh(pool, mesh, destination, mesh_parser, parser):
    names = mesh_names(mesh, mesh_parser)
    lookup = {m.materialName: m for m in pool.materialList}
    if len(lookup) != len(pool.materialList):
        raise ValueError('Duplicate material definitions')
    missing = set(names) - lookup.keys()
    if missing:
        raise ValueError(f'Missing material definitions: {sorted(missing)}')
    mdf = copy.deepcopy(pool)
    mdf.materialList = [copy.deepcopy(lookup[n]) for n in names]
    require_names(names, [m.materialName for m in mdf.materialList])
    # Empty GPBF tables still seek to this offset in the upstream serializer.
    if not any(m.gpbfBufferNameList for m in mdf.materialList):
        sizes = parser.SIZEDATA(32)
        offset = sizes.HEADER_SIZE + len(names)*sizes.MATERIAL_ENTRY_SIZE
        offset += sum(len(m.textureList)*sizes.TEXTURE_ENTRY_SIZE +
                      len(m.propertyList)*sizes.PROPERTY_ENTRY_SIZE for m in mdf.materialList)
        for mat in mdf.materialList:
            mat.GPUBufferOffset = offset
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    parser.writeMDF(mdf, str(destination))
    actual = parser.readMDF(str(destination))
    require_names(names, [m.materialName for m in actual.materialList])
    for before, after in zip(mdf.materialList, actual.materialList):
        if [(t.textureType, t.texturePath) for t in before.textureList] != [
                (t.textureType, t.texturePath) for t in after.textureList]:
            raise ValueError('Texture bindings changed during MDF serialization')


def validate_package(package, policy, mesh_parser, parser):
    checked = []
    for mesh, mdf in slot_pairs(package, policy):
        names = mesh_names(mesh, mesh_parser)
        require_names(names, [m.materialName for m in parser.readMDF(str(mdf)).materialList])
        checked.append({'mesh': str(mesh.relative_to(package)),
                        'mdf': str(mdf.relative_to(package)), 'materials': len(names)})
    return checked

"""Blender-hosted regression tests for preview materials and base-color discovery."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import bpy

SCRIPT_DIR = Path(os.environ.get('REPLACER_TEST_SCRIPTS', Path(__file__).resolve().parent))
sys.path.insert(0, str(SCRIPT_DIR))
import build_character_mod as build
import create_pose_alignment_workspace as pose


def image_node(tree, name, color_space='sRGB'):
    image = bpy.data.images.new(name, width=2, height=2, alpha=True)
    image.filepath = name
    image.colorspace_settings.name = color_space
    node = tree.nodes.new('ShaderNodeTexImage')
    node.image = image
    return node


class MaterialCompatibilityTests(unittest.TestCase):
    def tearDown(self):
        for material in list(bpy.data.materials):
            bpy.data.materials.remove(material, do_unlink=True)
        for image in list(bpy.data.images):
            bpy.data.images.remove(image, do_unlink=True)

    def test_preview_material_uses_node_types_not_display_names(self):
        material = bpy.data.materials.new('Guide')
        material.use_nodes = True
        shader = next(node for node in material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED')
        output = next(node for node in material.node_tree.nodes if node.type == 'OUTPUT_MATERIAL')
        shader.name = '用户重命名节点'
        output.name = '本地化输出'
        pose.configure_preview_material(material, (0.8, 0.2, 0.1, 1.0))
        self.assertEqual(shader.type, 'BSDF_PRINCIPLED')
        self.assertTrue(any(link.from_node == shader and link.to_node == output
                            for link in material.node_tree.links))
        for actual, expected in zip(shader.inputs['Base Color'].default_value,
                                    (0.8, 0.2, 0.1, 1.0)):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_preview_material_recreates_missing_shader_and_output(self):
        material = bpy.data.materials.new('EmptyGuide')
        material.use_nodes = True
        material.node_tree.nodes.clear()
        pose.configure_preview_material(material, (0.1, 0.4, 0.9, 1.0))
        shader = next(node for node in material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED')
        output = next(node for node in material.node_tree.nodes if node.type == 'OUTPUT_MATERIAL')
        self.assertTrue(any(link.from_node == shader and link.to_node == output
                            for link in material.node_tree.links))

    def test_nested_group_prefers_head_c_over_auxiliary_maps(self):
        material = bpy.data.materials.new('Head')
        material.use_nodes = True
        tree = material.node_tree
        shader = next(node for node in tree.nodes if node.type == 'BSDF_PRINCIPLED')
        group_tree = bpy.data.node_groups.new('ImportedShader', 'ShaderNodeTree')
        group_tree.interface.new_socket(name='Color', in_out='OUTPUT', socket_type='NodeSocketColor')
        group_output = group_tree.nodes.new('NodeGroupOutput')
        color = image_node(group_tree, 'Head_C.png')
        image_node(group_tree, 'Head_CSAR.png', 'Non-Color')
        image_node(group_tree, 'Head_MRA.png', 'Non-Color')
        image_node(group_tree, 'Head_N.png', 'Non-Color')
        group_tree.links.new(color.outputs['Color'], group_output.inputs['Color'])
        group = tree.nodes.new('ShaderNodeGroup')
        group.node_tree = group_tree
        tree.links.new(group.outputs['Color'], shader.inputs['Base Color'])
        self.assertEqual(build.base_image(material).name, 'Head_C.png')

    def test_unlinked_multimap_prefers_head_c(self):
        material = bpy.data.materials.new('HeadUnlinked')
        material.use_nodes = True
        for name, space in (
                ('Head_C.png', 'sRGB'), ('Head_CSAR.png', 'Non-Color'),
                ('Head_MRA.png', 'Non-Color'), ('Head_N.png', 'Non-Color')):
            image_node(material.node_tree, name, space)
        self.assertEqual(build.base_image(material).name, 'Head_C.png')

    def test_ambiguous_images_stop_instead_of_guessing(self):
        material = bpy.data.materials.new('Ambiguous')
        material.use_nodes = True
        image_node(material.node_tree, 'one.png')
        image_node(material.node_tree, 'two.png')
        with self.assertRaisesRegex(ValueError, '存在歧义'):
            build.base_image(material)

    def test_unique_moved_texture_is_recovered(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            moved = root / 'textures' / 'Head_C.png'
            moved.parent.mkdir()
            moved.write_bytes(b'not-an-image-but-path-resolution-is-testable')
            image = bpy.data.images.new('Missing', width=2, height=2)
            image.source = 'FILE'
            image.filepath = 'C:/old/location/Head_C.png'
            recovered = build.recover_missing_images([image], [root])
            self.assertEqual(Path(image.filepath).resolve(), moved.resolve())
            self.assertEqual(len(recovered), 1)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MaterialCompatibilityTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)

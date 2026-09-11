import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image


class DDSTests(unittest.TestCase):
    def test_blender_bottom_up_pixels_are_written_top_down(self):
        pixels = types.SimpleNamespace(foreach_get=lambda out: out.__setitem__(slice(None),
            [0,0,1,1, 1,1,0,1, 1,0,0,1, 0,1,0,1]))
        source = types.SimpleNamespace(size=(2,2), pixels=pixels)
        images = types.SimpleNamespace(load=lambda *a,**k: source, remove=lambda x: None)
        spec = importlib.util.spec_from_file_location('dds_under_test', Path(__file__).resolve().parents[1]/'scripts/dds_fallback.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'bpy':types.SimpleNamespace(data=types.SimpleNamespace(images=images))}):
            spec.loader.exec_module(module)
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp)/'test.dds'
                module.write_rgba8_dds('unused', path)
                with Image.open(path) as image:
                    self.assertEqual(image.getpixel((0,0)), (255,0,0,255))
                    self.assertEqual(image.getpixel((0,1)), (0,0,255,255))


if __name__ == '__main__':
    unittest.main()

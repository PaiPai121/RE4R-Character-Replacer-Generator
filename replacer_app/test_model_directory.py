import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import server
from server import browse_model_directory


class DirectoryTests(unittest.TestCase):
    def test_filters_and_preserves_unicode_paths(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)
            (path/'child').mkdir()
            (path/'角色.pmx').touch()
            (path/'texture.png').touch()
            result=browse_model_directory(str(path))
            self.assertEqual([e['name'] for e in result['entries']],['child','角色.pmx'])
            self.assertTrue(result['entries'][0]['directory'])
            self.assertEqual(result['entries'][1]['path'],str((path/'角色.pmx').resolve()))

    def test_relative_and_network_paths_rejected(self):
        for path in ('relative/path','\\\\server\\share'):
            with self.assertRaises(ValueError):browse_model_directory(path)

    def test_missing_folder_is_explicit_error(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(OSError):browse_model_directory(str(Path(root)/'missing'))

    def test_default_falls_back_when_packaged_source_model_is_absent(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            package = root / 'package'
            home = root / 'user-home'
            package.mkdir()
            home.mkdir()
            with patch.object(server, 'PROJECT', package), patch.object(Path, 'home', return_value=home), patch.dict('os.environ', {}, clear=True):
                result = browse_model_directory()
            self.assertEqual(Path(result['path']), home.resolve())


if __name__=='__main__':unittest.main()

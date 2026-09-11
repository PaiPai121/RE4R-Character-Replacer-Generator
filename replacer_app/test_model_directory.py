import tempfile
import json
import os
import threading
import time
import unittest
from unittest.mock import patch
from pathlib import Path
import server
from server import browse_model_directory, pick_model_with_native_dialog


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

    def test_native_picker_broker_request_acknowledgement_and_result(self):
        server.APP_DATA.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=server.APP_DATA) as root:
            broker = Path(root)
            model = broker / '测试人物.fbx'
            model.touch()

            def launcher_side():
                deadline = time.monotonic() + 3
                request = None
                while time.monotonic() < deadline and request is None:
                    request = next(broker.glob('*.request.json'), None)
                    time.sleep(.01)
                self.assertIsNotNone(request)
                request_id = request.name.removesuffix('.request.json')
                (broker / f'{request_id}.ack').write_text('ready', encoding='utf-8')
                (broker / f'{request_id}.result.json').write_text(json.dumps({
                    'ok': True, 'cancelled': False, 'path': str(model),
                    'name': model.name, 'directory': str(model.parent),
                }), encoding='utf-8')

            worker = threading.Thread(target=launcher_side)
            worker.start()
            with patch.dict(os.environ, {'REPLACER_NATIVE_PICKER_DIR': str(broker)}):
                result = pick_model_with_native_dialog()
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
            self.assertEqual(Path(result['path']), model.resolve())
            self.assertFalse(any(broker.glob('*.request.json')))
            self.assertFalse(any(broker.glob('*.result.json')))
            self.assertFalse(any(broker.glob('*.ack')))


if __name__=='__main__':unittest.main()

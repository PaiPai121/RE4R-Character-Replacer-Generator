import tempfile
import threading
import unittest
import json
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

import server


class StaticServerTests(unittest.TestCase):
    def setUp(self):
        self.httpd = server.ExclusiveThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def test_root_is_application_not_directory_listing(self):
        port = self.httpd.server_port
        with urlopen(f'http://127.0.0.1:{port}/', timeout=3) as response:
            body = response.read().decode('utf-8')
            self.assertEqual(response.headers.get_content_type(), 'text/html')
            self.assertIn('<title>RE4 · Character Replacer</title>', body)
            self.assertIn('<script src="/i18n.js"></script>', body)
            self.assertNotIn('Directory listing for /', body)

    def test_directory_listing_is_disabled(self):
        port = self.httpd.server_port
        with self.assertRaises(Exception):
            urlopen(f'http://127.0.0.1:{port}/missing/', timeout=3)

    def test_port_cannot_be_shared(self):
        with self.assertRaises(OSError):
            duplicate = server.ExclusiveThreadingHTTPServer(
                ('127.0.0.1', self.httpd.server_port), server.Handler)
            duplicate.server_close()

    def test_language_choice_is_shared_with_launcher_config(self):
        port = self.httpd.server_port
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'replacer-paths.json').write_text(json.dumps({'blender': 'C:/Blender/blender.exe'}), encoding='utf-8')
            request = Request(
                f'http://127.0.0.1:{port}/api/language',
                data=json.dumps({'language': 'en-US'}).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with patch.object(server, 'PROJECT', root), patch.object(server, 'source_revision', return_value=server.LOADED_REVISION):
                with urlopen(request, timeout=3) as response:
                    self.assertEqual(json.loads(response.read())['language'], 'en')
            saved = json.loads((root / 'replacer-paths.json').read_text(encoding='utf-8'))
            self.assertEqual(saved, {'blender': 'C:/Blender/blender.exe', 'language': 'en'})

    def test_download_path_accepts_only_project_and_short_build_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / 'project'
            build = root / 'short-jobs'
            outside = root / 'private.txt'
            project_file = project / 'work' / 'preview.png'
            build_file = build / '12345678' / 'output.zip'
            for path in (outside, project_file, build_file):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            with patch.object(server, 'PROJECT', project), patch.object(server, 'build_job_root', return_value=build.resolve()):
                self.assertEqual(server.resolve_download_path(project_file), project_file.resolve())
                self.assertEqual(server.resolve_download_path(build_file), build_file.resolve())
                with self.assertRaises(ValueError):
                    server.resolve_download_path(outside)


if __name__ == '__main__':
    unittest.main()

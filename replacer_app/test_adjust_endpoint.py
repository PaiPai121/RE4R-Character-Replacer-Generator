import json
import subprocess
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import Mock, patch

import server


class AdjustEndpointTests(unittest.TestCase):
    def setUp(self):
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:%s' % self.http.server_port

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()

    def post(self, blend):
        request = Request(self.url + '/api/open-blender',
                          data=json.dumps({'blend': str(blend)}).encode(),
                          headers={'Content-Type': 'application/json'})
        try:
            response = urlopen(request)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_launch_success_and_early_failure(self):
        with tempfile.NamedTemporaryFile(dir=server.PROJECT, suffix='.blend') as blend:
            process = Mock(pid=123)
            process.wait.side_effect = subprocess.TimeoutExpired('blender', 1)
            with patch.object(server, 'BLENDER', server.Path(__file__)), \
                    patch.object(server.subprocess, 'Popen', return_value=process) as spawn:
                status, result = self.post(blend.name)
                self.assertEqual(status, 200)
                self.assertEqual(result['pid'], 123)
                self.assertEqual(result['blend'], str(server.Path(blend.name).resolve()))
                self.assertIn(result['blend'], spawn.call_args.args[0])
                process.wait.side_effect = None
                process.wait.return_value = 1
                status, result = self.post(blend.name)
                self.assertEqual(status, 500)
                self.assertFalse(result['ok'])

    def test_missing_file_and_stale_server_do_not_launch(self):
        with patch.object(server.subprocess, 'Popen') as spawn:
            status, _ = self.post(server.PROJECT / 'missing-pose.blend')
            self.assertEqual(status, 404)
            with patch.object(server, 'LOADED_REVISION', 'old'):
                status, _ = self.post(server.PROJECT / 'missing-pose.blend')
                self.assertEqual(status, 409)
            spawn.assert_not_called()


if __name__ == '__main__':
    unittest.main()

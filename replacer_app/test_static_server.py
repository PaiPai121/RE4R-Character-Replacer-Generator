import threading
import unittest
from urllib.request import urlopen

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
            self.assertIn('<title>RE4 · 人物替换</title>', body)
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


if __name__ == '__main__':
    unittest.main()

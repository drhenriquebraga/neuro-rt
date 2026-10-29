import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from neuro_rt.server import make_server
from neuro_rt.service import Service, Settings
from test_pipeline import TEMP_ROOT


class HttpTests(unittest.TestCase):
    def test_origin_token_and_static_traversal_guards(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            (root / 'web').mkdir()
            (root / 'web/index.html').write_text('<h1>Synthetic</h1>')
            service = Service(Settings(root))
            server = make_server(service, port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}/neuro/'
            try:
                status = json.load(urllib.request.urlopen(base + 'api/status'))
                self.assertEqual(status['module'], 'neuro-rt')
                for headers in ({}, {'X-Neuro-Token':status['token'],'Origin':'https://example.com'}):
                    req = urllib.request.Request(base + 'api/jobs', data=b'{}', headers=headers)
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(req)
                    self.assertEqual(caught.exception.code, 403)
                req = urllib.request.Request(base + 'api/jobs',data=b'{}',
                      headers={'X-Neuro-Token':status['token'],'Origin':base.removesuffix('/neuro/')})
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(req)
                self.assertEqual(caught.exception.code, 400)
                for route in ('../neuro_rt.local.json','api/jobs/unknown/artifacts/worker.log'):
                    with self.assertRaises(urllib.error.HTTPError):
                        urllib.request.urlopen(base + route)
                with urllib.request.urlopen(base) as response:
                    self.assertIn("frame-ancestors 'self'",response.headers['Content-Security-Policy'])
            finally:
                server.shutdown()
                server.server_close()
                service.close()
                thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()

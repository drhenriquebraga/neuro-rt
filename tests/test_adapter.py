import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@unittest.skipUnless(importlib.util.find_spec('fastapi') and importlib.util.find_spec('httpx'),
                     'Este teste roda pelo Python do Local Suite, com FastAPI e httpx.')
class AdapterTests(unittest.TestCase):
    def test_mounted_iframe_and_api_share_origin_and_guards(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from integration.radai_neuro import montar
        app = FastAPI()
        service = montar(app, ROOT)
        self.assertIs(montar(app, ROOT), service)
        with TestClient(app) as client:
            response = client.get('/neuro/')
            self.assertEqual(response.status_code, 200)
            self.assertIn('NeuroRT', response.text)
            self.assertEqual(client.get('/neuro/app.js').status_code, 200)
            status = client.get('/neuro/api/status').json()
            self.assertEqual(status['module'], 'neuro-rt')
            self.assertEqual(client.get('/neuro/api/status',headers={'Host':'evil.example'}).status_code,403)
            self.assertEqual(client.post('/neuro/api/jobs', json={}).status_code, 403)
            headers = {'X-Neuro-Token':status['token'],'Origin':'http://testserver'}
            self.assertEqual(client.post('/neuro/api/jobs', json={},headers=headers).status_code, 400)
            headers['Origin'] = 'https://untrusted.example'
            self.assertEqual(client.post('/neuro/api/jobs', json={},headers=headers).status_code, 403)


if __name__ == '__main__':
    unittest.main()

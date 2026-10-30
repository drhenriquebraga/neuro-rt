"""Synthetic HTTP coverage: no model, DICOM or worker is invoked."""
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest


@unittest.skipUnless(importlib.util.find_spec('fastapi') and importlib.util.find_spec('httpx'),
                     'Use o Python do host com FastAPI/httpx.')
class PluginAccessTests(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.testclient import TestClient
        from integration.plugin_access import attach
        from neuro_rt.plugin_consent import policy
        base = Path(__file__).resolve().parents[1] / 'runtime/test-tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.config = Path(self.tmp.name) / 'config'
        app = FastAPI()
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        # The production host loads plugins after it has served requests. This
        # must not attempt app.add_middleware on an already started ASGI app.
        self.assertEqual(self.client.get('/unrelated').status_code, 404)
        self.assertIsNotNone(app.middleware_stack)
        from fastapi import APIRouter
        router = APIRouter(prefix='/neuro')

        def local(request):
            if request.url.hostname != 'testserver':
                raise HTTPException(403)

        async def action(request, maximum=8192):
            local(request)
            if request.headers.get('x-neuro-token') != 'synthetic-token':
                raise HTTPException(403)
            return await request.json()

        protect = attach(app, router, SimpleNamespace(token='synthetic-token'), self.config, local, action,
                         integrated=False)
        app.include_router(router)
        @app.get('/neuro/')
        def landing():
            return {'landing': True}
        @app.get('/nidus/projecao')
        def nidus():
            return {'nidus': True}
        @app.post('/api/nidus/abrir')
        def nidus_api():
            return {'opened': True}
        @app.post('/neuro/api/studies')
        @app.post('/neuro/api/jobs')
        @app.post('/neuro/api/selection')
        @app.post('/neuro/api/studies/synthetic/retry')
        def forbidden_worker():
            raise AssertionError('Um motor não deve ser invocado nesta entrega.')
        protect()
        self.policy = policy()
        self.payload = {key: self.policy[key] for key in ('version', 'digest')}
        self.payload['accepted'] = True

    def test_first_use_blocks_direct_nidus_and_api_until_explicit_acceptance(self):
        self.assertEqual(self.client.get('/nidus/projecao', follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.post('/api/nidus/abrir', json={}).status_code, 428)
        page = self.client.get('/neuro/onboarding')
        self.assertEqual(page.status_code, 200)
        self.assertIn(self.policy['digest'], page.text)
        self.assertNotIn('type="checkbox" checked', page.text)
        self.assertEqual(self.client.post('/neuro/api/consent', json=self.payload).status_code, 403)
        headers = {'X-Neuro-Token': 'synthetic-token'}
        response = self.client.post('/neuro/api/consent', json=self.payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/nidus/projecao').json(), {'nidus': True})
        self.assertEqual(self.client.post('/api/nidus/abrir', json={}).status_code, 200)

    def test_direct_neural_routes_and_mutations_never_reach_workers(self):
        for tool in ('glioma', 'metastasis', 'meningioma', 'anatomia'):
            for path in ('/neuro/'+tool, '/neuro/?category='+tool,
                         '/neuro/?category=other&category='+tool, '/neuro/?category='+tool+'&category='+tool):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 503)
                    self.assertIn('em construção', response.text)
        for path in ('/neuro/api/studies', '/neuro/api/jobs', '/neuro/api/selection',
                     '/neuro/api/studies/synthetic/retry'):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, json={},
                    headers={'X-Neuro-Token': 'synthetic-token'}).status_code, 409)

    def test_consent_status_keeps_installation_separate_and_returns_tool_contract(self):
        response = self.client.get('/neuro/api/consent').json()
        self.assertFalse(response['first_use'])
        self.assertFalse(response['installation'])
        self.assertEqual([t['id'] for t in response['tools'] if t['enabled']], ['nidus'])
        self.client.post('/neuro/api/consent', json=self.payload,
                         headers={'X-Neuro-Token': 'synthetic-token'})
        response = self.client.get('/neuro/api/consent').json()
        self.assertTrue(response['first_use'])
        self.assertFalse(response['installation'])


if __name__ == '__main__':
    unittest.main()

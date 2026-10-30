"""Explicit test-phase entry and API guards; never invokes an inference engine."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

@unittest.skipUnless(importlib.util.find_spec('fastapi') and
                     (importlib.util.find_spec('httpx') or importlib.util.find_spec('httpx2')),
                     'Use o Python do host com FastAPI e seu cliente HTTP de testes.')
class BetaAccessTests(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI, APIRouter, HTTPException, Request
        from fastapi.testclient import TestClient
        from integration.plugin_access import attach
        from neuro_rt import plugin_consent
        base = Path(__file__).resolve().parents[1] / 'runtime/test-tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.config = Path(self.tmp.name)
        plugin_consent.accept(self.config, 'first_use', dict(plugin_consent.policy(), accepted=True))
        app, router = FastAPI(), APIRouter(prefix='/neuro')
        self.service = SimpleNamespace(token='test-only-token')
        def local(request):
            if request.url.hostname != 'testserver': raise HTTPException(403)
        async def action(request, maximum=8192):
            local(request)
            if request.headers.get('x-neuro-token') != self.service.token: raise HTTPException(403)
            return await request.json()
        protect = attach(app, router, self.service, self.config, local, action, integrated=False)
        app.include_router(router)
        for path in ('/neuro/nidus', '/neuro/glioma', '/neuro/metastasis', '/neuro/meningioma', '/neuro/anatomia'):
            app.add_api_route(path, lambda: {'page': True})
        @app.post('/api/nidus/tubos')
        def tubes(): return {'allowed': True}
        protect()
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def accept(self, tool):
        policy = self.client.get('/neuro/api/testing/' + tool).json()['policy']
        return self.client.post('/neuro/api/testing/' + tool,
            json={'accepted': True, 'version': policy['version'], 'digest': policy['digest']},
            headers={'X-Neuro-Token': self.service.token})

    def test_each_card_entry_opens_a_fresh_unchecked_modal_and_cancel_returns_home(self):
        for tool in ('nidus', 'glioma', 'metastasis', 'meningioma', 'anatomia'):
            with self.subTest(tool=tool):
                page = self.client.get('/neuro/testing/' + tool)
                self.assertEqual(page.status_code, 200)
                self.assertIn('<dialog', page.text)
                self.assertIn('Henrique Braga', page.text)
                self.assertIn('feedback', page.text)
                self.assertNotIn('type="checkbox" checked', page.text)
                self.assertIn('Cancelar', page.text)
                self.assertEqual(self.accept(tool).status_code, 200)
                self.assertIn('<dialog', self.client.get('/neuro/testing/' + tool).text)

    def test_direct_url_and_nidus_api_require_tool_acknowledgement(self):
        self.assertEqual(self.client.get('/neuro/nidus', follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.post('/api/nidus/tubos', json={}).status_code, 428)
        self.assertEqual(self.accept('nidus').status_code, 200)
        self.assertEqual(self.client.get('/neuro/nidus').status_code, 200)
        self.assertEqual(self.client.post('/api/nidus/tubos', json={}).status_code, 200)
        self.assertEqual(self.client.get('/neuro/glioma', follow_redirects=False).status_code, 303)

    def test_unchecked_stale_or_unprotected_acceptance_never_unlocks(self):
        path = '/neuro/api/testing/glioma'
        policy = self.client.get(path).json()['policy']
        payload = {'accepted': True, 'version': policy['version'], 'digest': policy['digest']}
        self.assertEqual(self.client.post(path, json=payload).status_code, 403)
        for changes in ({'accepted': False}, {'accepted': 1}, {'digest': '0' * 64}):
            response = self.client.post(path, json=dict(payload, **changes),
                headers={'X-Neuro-Token': self.service.token})
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get('/neuro/glioma', follow_redirects=False).status_code, 303)

    def test_grant_cookie_is_http_only_scoped_and_api_does_not_send_feedback(self):
        response = self.accept('glioma')
        self.assertEqual(response.status_code, 200)
        cookie = response.headers['set-cookie']
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=strict', cookie)
        self.assertIn('Path=/', cookie)
        self.assertEqual(response.json()['route'], '/neuro/glioma')
        self.assertFalse(list(self.config.glob('*testing*')), 'No patient/operator/feedback file is written')

    def test_global_first_use_remains_required_before_testing(self):
        (self.config / 'consent-first_use.json').unlink()
        self.assertEqual(self.client.get('/neuro/testing/glioma', follow_redirects=False).status_code, 303)
        self.assertEqual(self.accept('glioma').status_code, 428)

    def test_model_guard_allows_anatomy_in_tumor_tool_but_not_an_unaccepted_tumor(self):
        from fastapi import HTTPException
        from starlette.requests import Request
        self.accept('glioma')
        scope = {'type': 'http', 'headers': [(b'cookie', str(self.client.cookies).encode())]}
        # Build the actual browser Cookie header, without the client's display repr.
        scope['headers'] = [(b'cookie', '; '.join(k+'='+v for k,v in self.client.cookies.items()).encode())]
        request = Request(scope)
        catalog = {'g': {'groups': ['glioma']}, 'a': {'groups': ['anatomia']},
                   'm': {'groups': ['metastasis']}}
        self.service.testing_access.require_models(request, ['g', 'a'], catalog)
        with self.assertRaises(HTTPException) as denied:
            self.service.testing_access.require_models(request, ['m'], catalog)
        self.assertEqual(denied.exception.status_code, 428)

    def test_real_adapter_does_not_allow_selection_or_submit_to_bypass_testing(self):
        from unittest.mock import patch
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from integration.radai_neuro import montar
        from neuro_rt import plugin_consent
        root = Path(__file__).resolve().parents[1]
        config = self.config / 'adapter/plugin-consent'
        plugin_consent.accept(config, 'first_use', dict(plugin_consent.policy(), accepted=True))
        calls = []
        study = SimpleNamespace(catalog={'g': {'groups': ['glioma']}},
            selection=lambda *args: calls.append('selection') or {},
            submit=lambda *args: calls.append('submit') or {})
        service = SimpleNamespace(token='adapter-token', studies=study, close=lambda: None)
        settings = SimpleNamespace(data_dir=self.config/'adapter')
        app = FastAPI()
        with patch('neuro_rt.service.Service', return_value=service), patch('neuro_rt.service.Settings', return_value=settings):
            montar(app, root)
        with TestClient(app) as client:
            headers = {'X-Neuro-Token': 'adapter-token'}
            self.assertEqual(client.post('/neuro/api/selection', json={'category':'glioma','tickets':[]}, headers=headers).status_code, 428)
            self.assertEqual(client.post('/neuro/api/studies', json={'studies':[{'model_ids':['g']}]}, headers=headers).status_code, 428)
            self.assertEqual(calls, [])
            p = client.get('/neuro/api/testing/glioma').json()['policy']
            client.post('/neuro/api/testing/glioma', json=dict(p, accepted=True), headers=headers)
            self.assertEqual(client.post('/neuro/api/selection', json={'category':'glioma','tickets':[]}, headers=headers).status_code, 200)
            self.assertEqual(client.post('/neuro/api/studies', json={'studies':[{'model_ids':['g']}]}, headers=headers).status_code, 202)
            self.assertEqual(calls, ['selection', 'submit'])

if __name__ == '__main__': unittest.main()

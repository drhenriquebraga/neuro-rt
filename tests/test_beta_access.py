"""Explicit test-phase entry and API guards; never invokes an inference engine."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

@unittest.skipUnless(importlib.util.find_spec('fastapi') and
                     (importlib.util.find_spec('httpx') or importlib.util.find_spec('httpx2')),
                     'Use o Python do host com FastAPI e seu cliente HTTP de testes.')
class BetaAccessTests(unittest.TestCase):
    def setUp(self):
        from neuro_rt import plugin_consent
        base = Path(__file__).resolve().parents[1] / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='beta-access-', dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.config = Path(self.tmp.name)
        plugin_consent.accept(self.config, 'first_use', dict(plugin_consent.policy(), accepted=True))
        self.service, self.client = self.mount(self.config)

    def mount(self, config):
        from fastapi import FastAPI, APIRouter, HTTPException, Request
        from fastapi.testclient import TestClient
        from integration.plugin_access import attach
        app, router = FastAPI(), APIRouter(prefix='/neuro')
        service = SimpleNamespace(token='test-only-token')
        def local(request):
            if request.url.hostname != 'testserver': raise HTTPException(403)
        async def action(request, maximum=8192):
            local(request)
            if request.headers.get('x-neuro-token') != service.token: raise HTTPException(403)
            return await request.json()
        protect = attach(app, router, service, config, local, action, integrated=False)
        app.include_router(router)
        for path in ('/neuro/nidus', '/neuro/glioma', '/neuro/metastasis', '/neuro/meningioma', '/neuro/anatomia'):
            app.add_api_route(path, lambda: {'page': True})
        @app.post('/api/nidus/tubos')
        def tubes(): return {'allowed': True}
        protect()
        client = TestClient(app)
        self.addCleanup(client.close)
        return service, client

    def accept(self, tool):
        policy = self.client.get('/neuro/api/testing/' + tool).json()['policy']
        return self.client.post('/neuro/api/testing/' + tool,
            json={'accepted': True, 'version': policy['version'], 'digest': policy['digest']},
            headers={'X-Neuro-Token': self.service.token})

    def test_each_card_prompts_once_per_current_policy(self):
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
                response = self.client.get('/neuro/testing/' + tool, follow_redirects=False)
                self.assertEqual(response.status_code, 303)
                self.assertEqual(response.headers['location'], '/neuro/' + tool)
                self.assertTrue(self.client.get('/neuro/api/testing/' + tool).json()['accepted'])

    def test_direct_url_and_nidus_api_require_tool_acknowledgement(self):
        self.assertEqual(self.client.get('/neuro/nidus', follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.post('/api/nidus/tubos', json={}).status_code, 428)
        self.assertEqual(self.accept('nidus').status_code, 200)
        self.assertEqual(self.client.get('/neuro/nidus').status_code, 200)
        self.assertEqual(self.client.post('/api/nidus/tubos', json={}).status_code, 200)
        self.assertEqual(self.client.post('/api/nidus/tubos', json={},
            headers={'Origin': 'https://untrusted.example'}).status_code, 403)
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

    def test_acceptance_survives_remount_and_is_isolated_by_tool_and_installation(self):
        from neuro_rt import plugin_consent
        response = self.accept('nidus')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('set-cookie', response.headers)
        self.assertEqual(response.json()['route'], '/neuro/nidus')
        _, restarted = self.mount(self.config)
        self.assertEqual(restarted.get('/neuro/nidus').status_code, 200)
        self.assertEqual(restarted.post('/api/nidus/tubos', json={}).status_code, 200)
        self.assertIn('<dialog', restarted.get('/neuro/testing/glioma').text)
        other = self.config / 'other-installation'
        plugin_consent.accept(other, 'first_use', dict(plugin_consent.policy(), accepted=True))
        _, separate = self.mount(other)
        self.assertIn('<dialog', separate.get('/neuro/testing/nidus').text)
        self.assertEqual(separate.post('/api/nidus/tubos', json={}).status_code, 428)

    def test_invalid_receipt_requires_new_explicit_acceptance(self):
        self.assertEqual(self.accept('nidus').status_code, 200)
        receipt = self.config / 'consent-testing-nidus.json'
        value = json.loads(receipt.read_text(encoding='utf-8'))
        self.assertEqual(set(value), {'schema', 'tool', 'version', 'digest', 'accepted', 'accepted_at'})
        for invalid in (dict(value, tool='glioma'), dict(value, version='0'),
                        dict(value, digest='0' * 64), dict(value, accepted=1), None):
            with self.subTest(invalid=invalid):
                receipt.write_text(json.dumps(invalid) if invalid is not None else '{', encoding='utf-8')
                page = self.client.get('/neuro/testing/nidus')
                self.assertIn('<dialog', page.text)
                self.assertFalse(self.client.get('/neuro/api/testing/nidus').json()['accepted'])
                self.assertEqual(self.client.post('/api/nidus/tubos', json={}).status_code, 428)
        self.assertEqual(self.accept('nidus').status_code, 200)
        self.assertEqual(self.client.post('/api/nidus/tubos', json={}).status_code, 200)

    def test_failed_receipt_write_leaves_tool_locked_and_allows_retry(self):
        receipt = self.config / 'consent-testing-nidus.json'
        receipt.mkdir()
        self.assertEqual(self.accept('nidus').status_code, 503)
        self.assertFalse(list(self.config.glob('.consent-testing-*')))
        self.assertEqual(self.client.post('/api/nidus/tubos', json={}).status_code, 428)
        receipt.rmdir()
        self.assertEqual(self.accept('nidus').status_code, 200)

    def test_global_first_use_remains_required_before_testing(self):
        self.assertEqual(self.accept('nidus').status_code, 200)
        (self.config / 'consent-first_use.json').unlink()
        self.assertEqual(self.client.get('/neuro/testing/glioma', follow_redirects=False).status_code, 303)
        self.assertEqual(self.accept('glioma').status_code, 428)
        self.assertEqual(self.client.post('/api/nidus/tubos', json={}).status_code, 428)

    def test_installation_receipt_satisfies_first_use_without_writing_another_receipt(self):
        from neuro_rt import plugin_consent
        (self.config / 'consent-first_use.json').unlink()
        plugin_consent.accept(self.config, 'installation', dict(plugin_consent.policy(), accepted=True))
        response = self.client.get('/neuro/onboarding', follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers['location'], '/neuro/')
        self.assertIn('<dialog', self.client.get('/neuro/testing/glioma').text)
        self.assertEqual(self.accept('glioma').status_code, 200)
        self.assertTrue(self.client.get('/neuro/api/consent').json()['first_use'])
        self.assertFalse((self.config / 'consent-first_use.json').exists())

    def test_model_guard_allows_anatomy_in_tumor_tool_but_not_an_unaccepted_tumor(self):
        from fastapi import HTTPException
        self.accept('glioma')
        request = {'type': 'http', 'headers': []}
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
            payload = dict(p, accepted=True)
            foreign = dict(headers, Origin='https://untrusted.example')
            self.assertEqual(client.post('/neuro/api/testing/glioma', json=payload, headers=foreign).status_code, 403)
            self.assertEqual(client.post('/neuro/api/selection', json={'category':'glioma','tickets':[]}, headers=headers).status_code, 428)
            self.assertEqual(client.post('/neuro/api/testing/glioma', json=payload, headers=headers).status_code, 200)
            self.assertEqual(client.post('/neuro/api/selection', json={'category':'glioma','tickets':[]}, headers=foreign).status_code, 403)
            self.assertEqual(client.post('/neuro/api/selection', json={'category':'glioma','tickets':[]}, headers=headers).status_code, 200)
            self.assertEqual(client.post('/neuro/api/studies', json={'studies':[{'model_ids':['g']}]}, headers=headers).status_code, 202)
            self.assertEqual(calls, ['selection', 'submit'])

if __name__ == '__main__': unittest.main()

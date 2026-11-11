"""Code-only base profile keeps Nidus usable while models remain optional."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from host_setup_fixtures import host_setup
from neuro_rt import external_install as external, install_state
from neuro_rt.plugin_paths import resolve_plugin_paths
from neuro_rt.service import Service, Settings


class CodeOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='neuro-code-only-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.host = self.root / 'suite'
        self.host.mkdir()
        for name in ('radai_panel.py', 'radai_ui.py'):
            (self.host / name).write_text('# synthetic host\n')
        (self.host / 'entrega.txt').write_text('VERSAO=8.17\n')
        self.source = self.root / 'source'

        def optional(manifest, files):
            module = json.loads(files['code/module.json'])
            module.update(host_min_version='8.17', base_tools=['nidus'],
                          enabled_tools=['nidus', 'glioma', 'metastasis', 'meningioma', 'anatomia'],
                          resource_recipe='catalog/resource_recipe.json')
            files['code/module.json'] = json.dumps(module).encode()
            files['code/catalog/resource_recipe.json'] = json.dumps({
                'schema': 'neuro-rt/resource-recipe/1', 'wheels': [], 'models': []}).encode()

        self.package = host_setup(self.root, '1.3.2', mutate=optional)
        with zipfile.ZipFile(self.package['path']) as archive:
            archive.extractall(self.source)
        manifest = json.loads((self.source / 'release-manifest.json').read_text())
        patcher = patch.object(external, 'TRUSTED_CODE_INVENTORIES',
                               {external.code_inventory_sha256(manifest)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def plan(self, code_only=True):
        return external.prepare_external_plan(
            {'mode': 'local', 'local_source_accepted': True, 'code_only': code_only},
            source_folder=self.source)

    def run_plan(self, plan):
        with patch('importlib.metadata.version', return_value='1.0'):
            return external.run_external(plan, None, suite_root=self.host, host_python=sys.executable)

    def test_code_only_installs_without_models_downloads_or_consent(self):
        with patch.object(external, '_prepare_resources', side_effect=AssertionError('resources')), \
                patch('urllib.request.urlopen', side_effect=AssertionError('network')):
            self.assertEqual(self.run_plan(self.plan()), {'state': 'ready', 'active_version': '1.3.2'})
        plugin = self.host / 'Plugins/NEURO RT'
        state = json.loads((plugin / 'installation.json').read_text())
        self.assertIsNone(state['resources'])
        self.assertFalse((plugin / 'config/consent-installation.json').exists())
        with patch('importlib.metadata.version', return_value='1.0'):
            paths = resolve_plugin_paths(self.host, state, host_python=sys.executable)
        service = Service(Settings(paths.code_dir, plugin_paths=paths))
        self.addCleanup(service.close)
        self.assertEqual({tool['id'] for tool in service.tools() if tool['enabled']}, {'nidus'})
        self.assertIsNone(service.settings.runtime_python('raidionics-onnx'))

    def test_full_preparation_remains_default_and_failure_preserves_base(self):
        self.run_plan(self.plan())
        pointer = self.host / 'Plugins/NEURO RT/installation.json'
        before = json.loads(pointer.read_text())
        with patch.object(external, '_prepare_resources',
                          side_effect=OSError('synthetic missing download')) as prepare:
            with self.assertRaises(OSError):
                self.run_plan(self.plan(False))
        self.assertEqual(prepare.call_count, 1)
        state = json.loads(pointer.read_text())
        self.assertEqual(state['active_version'], before['active_version'])
        self.assertIsNone(state['resources'])

    def test_invalid_optional_weight_receipt_does_not_block_the_base_ui(self):
        self.run_plan(self.plan())
        pointer = self.host / 'Plugins/NEURO RT/installation.json'
        state = json.loads(pointer.read_text())
        state.update(state='failed', resources={'schema': 'damaged-optional-receipt'})
        pointer.write_text(json.dumps(state))
        before = pointer.read_bytes()
        with patch('importlib.metadata.version', return_value='1.0'):
            with self.assertRaises(ValueError):
                resolve_plugin_paths(self.host, state, host_python=sys.executable)
            paths = resolve_plugin_paths(self.host, state, host_python=sys.executable,
                                         allow_base_only=True)
        service = Service(Settings(paths.code_dir, plugin_paths=paths))
        self.addCleanup(service.close)
        self.assertEqual(service.settings.installation_state, 'ready')
        self.assertIsNone(paths.resources)
        self.assertEqual({tool['id'] for tool in service.tools() if tool['enabled']}, {'nidus'})
        self.assertEqual(service.weights_status()['state'], 'missing')
        self.assertEqual(pointer.read_bytes(), before)

    def test_plan_rejects_non_boolean_code_only(self):
        for value in (1, 'true', None, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.plan(value)

    def test_legacy_full_plan_without_code_only_still_validates(self):
        plan = self.plan(False)
        del plan['code_only']
        external._validate_plan(plan)

    def test_base_buti_enables_only_anatomy_in_addition_to_nidus(self):
        settings = SimpleNamespace(plugin_paths=SimpleNamespace(), resources=None,
                                   host_app=self.host, host_python=sys.executable)
        service = Service.__new__(Service)
        service.settings = settings
        service.studies = SimpleNamespace(catalog={'cranio_buti': {}})
        with patch('integration.buti_host.capabilities',
                   return_value={'cranio_buti': {'available': True}}):
            self.assertEqual({tool['id'] for tool in service.tools() if tool['enabled']},
                             {'nidus', 'anatomia'})

    def test_minipage_opens_before_consent_and_nidus_requires_use_consent(self):
        from fastapi import FastAPI, APIRouter
        from fastapi.testclient import TestClient
        from integration.plugin_access import attach

        app, router = FastAPI(), APIRouter(prefix='/neuro')
        service = SimpleNamespace(token='synthetic-token', tool_available=lambda ident: ident == 'nidus')
        async def action(request, maximum):
            return await request.json()
        guard = attach(app, router, service, self.root / 'consent', lambda request: None, action, integrated=True)
        app.include_router(router)
        app.add_api_route('/neuro/', lambda: {'mini': True})
        app.add_api_route('/neuro/nidus', lambda: {'tool': True})
        app.add_api_route('/neuro/glioma', lambda: {'tool': True})
        guard()
        with TestClient(app) as client:
            self.assertEqual(client.get('/neuro/', follow_redirects=False).status_code, 200)
            nidus = client.get('/neuro/nidus', follow_redirects=False)
            self.assertEqual(nidus.status_code, 303)
            self.assertEqual(nidus.headers['location'], '/neuro/onboarding')
            missing = client.get('/neuro/glioma', follow_redirects=False)
            self.assertEqual(missing.status_code, 303)
            self.assertEqual(missing.headers['location'], '/neuro/')


if __name__ == '__main__':
    unittest.main()

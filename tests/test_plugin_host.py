import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False

HOST_APP = Path(__file__).resolve().parents[2] / 'AUTO_CONTORNO' / 'app'
sys.path.insert(0, str(HOST_APP))
spec = importlib.util.spec_from_file_location('host_neuro_entry_test', HOST_APP / 'radai_plugins.py')
HOST = importlib.util.module_from_spec(spec)
spec.loader.exec_module(HOST)


@unittest.skipUnless(HTTP_AVAILABLE, 'Executar esta bateria pelo Python do Local Suite, com FastAPI/httpx.')
class PluginHostTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = FastAPI()
        self.app.calls = 0
        from neuro_rt.plugin_update import ReleaseClient
        def offline(*a, **k):
            raise OSError('offline fixture')
        self.cfg = {'suite_root': self.root, 'neuro_host_version': '8.10',
                    'neuro_release_client': ReleaseClient(fetch_json=offline)}

    def ready(self):
        root = self.root / 'Plugins/NEURO RT'
        code = root / 'versions/0.3.0'
        (code / 'integration').mkdir(parents=True)
        manifest = {'schema': 'neuro-rt/plugin-manifest/1', 'id': 'neuro-rt',
                    'version': '0.3.0', 'host_contract': HOST.HOST_CONTRACT,
                    'host_min_version': '8.10', 'adapter': 'integration/adapter.py:montar'}
        (code / 'module.json').write_text(json.dumps(manifest))
        (code / 'integration/adapter.py').write_text(
            'def montar(app, root, host_services=None):\n'
            '    app.calls += 1\n    app.state.received_services = host_services\n'
            '    return object()\n')
        files = [{'path': 'code/' + path.relative_to(code).as_posix(),
                  'size': path.stat().st_size,
                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                 for path in code.rglob('*') if path.is_file()]
        (code / 'release-manifest.json').write_text(json.dumps({
            'schema': 'neuro-rt/release-package/1', 'plugin_id': 'neuro-rt',
            'version': '0.3.0', 'files': files}))
        (root / 'installation.json').write_text(json.dumps({
            'schema': 'neuro-rt/installation/1', 'state': 'ready', 'active_version': '0.3.0'}))
        self.cfg['neuro_host_services'] = SimpleNamespace()
        return code

    def await_load(self, entry, client=None):
        (client or TestClient(self.app)).get('/api/plugins/neuro-rt')
        self.assertTrue(entry['load_complete'].wait(10), 'background discovery did not finish')

    def confirmed_install_payload(self, status):
        # Successful synthetic requests acknowledge the exact policy published by
        # the current trusted host bootstrap; security/refusal cases stay bare.
        policy = status['consent']['policy']
        return {'confirm': True, 'consent': {'accepted': True,
                'version': policy['version'], 'digest': policy['digest']}}

    def test_absent_startup_never_imports_neuro_or_science_and_is_idempotent(self):
        before = set(sys.modules)
        first = HOST.montar(self.app, self.cfg)
        second = HOST.montar(self.app, self.cfg)
        self.assertIs(first, second)
        paths = [r.path for r in self.app.routes]
        self.assertEqual(1, paths.count('/neuro'))
        new = set(sys.modules) - before
        self.assertFalse(any(name.startswith(('neuro_rt', 'numpy', 'torch', 'SimpleITK')) for name in new))
        client = TestClient(self.app)
        self.assertEqual('absent', client.get('/api/plugins/neuro-rt').json()['state'])
        with patch('radai_menu.aplicar', side_effect=lambda p, _: p):
            page = client.get('/neuro')
        self.assertEqual(200, page.status_code)
        self.assertIn('ainda não está instalado', page.text)
        self.assertIn('no-store', page.headers['cache-control'])

    def test_first_install_browser_tracks_restart_and_new_session(self):
        import os
        import shutil
        import subprocess
        HOST.montar(self.app, self.cfg)
        with patch('radai_menu.aplicar', side_effect=lambda p, _: p):
            page = TestClient(self.app).get('/neuro').text
        self.assertIn('data-neuro-install="1"', page)
        self.assertIn('window.NeuroPluginUpdate', page)
        output = self.root / 'first-install.html'
        output.write_text(page, encoding='utf-8')
        env = dict(os.environ, NEURO_INSTALL_HTML=str(output))
        run = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('plugin_install_ui_browser.cjs'))],
                             capture_output=True, timeout=60, env=env)
        self.assertEqual(run.returncode, 0, run.stderr.decode(errors='replace')[-3000:])
        print(run.stdout.decode(errors='replace').strip())

    def test_home_startup_does_not_even_load_installer_bootstrap(self):
        self.ready()
        with patch('radai_neuro_install._load_private_installer') as load:
            HOST.montar(self.app, self.cfg)
        load.assert_not_called()

    def test_ready_mounts_once_and_carries_services_to_real_adapter(self):
        self.ready()
        entry = HOST.montar(self.app, self.cfg)
        HOST.montar(self.app, self.cfg)
        self.await_load(entry)
        self.assertEqual(1, self.app.calls)
        self.assertIs(self.cfg['neuro_host_services'], self.app.state.received_services)
        client = TestClient(self.app)
        self.assertEqual('/neuro/', client.get('/neuro', follow_redirects=False).headers['location'])
        self.assertEqual('/nidus/projecao', client.get('/neuro/nidus', follow_redirects=False).headers['location'])
        for category in ('glioma', 'metastasis', 'meningioma', 'anatomia'):
            response = client.get('/neuro/' + category, follow_redirects=False)
            self.assertEqual('/neuro/?category=' + category, response.headers['location'])

    def test_corrupt_and_incompatible_never_execute_plugin(self):
        code = self.ready()
        self.cfg['neuro_host_version'] = '8.9'
        entry = HOST.montar(self.app, self.cfg)
        self.await_load(entry)
        self.assertEqual('incompatible', entry['installation']['state'])
        self.assertEqual(0, self.app.calls)
        (code / 'integration/adapter.py').write_text('raise AssertionError("must not execute")')
        self.assertEqual('failed', HOST.discover_plugin(self.root, host_info={
            'contract': HOST.HOST_CONTRACT, 'version': '8.10'})['state'])

    def test_install_requires_local_same_origin_token_confirmation_and_real_handler(self):
        HOST.montar(self.app, self.cfg)
        client = TestClient(self.app)
        endpoint = '/api/plugins/neuro-rt/install'
        self.assertEqual(403, client.post(endpoint, json={'confirm': True}).status_code)
        status = client.get('/api/plugins/neuro-rt').json()
        token = status['token']
        headers = {'X-Neuro-Plugin-Token': token, 'Origin': 'https://external.test'}
        self.assertEqual(403, client.post(endpoint, headers=headers, json={'confirm': True}).status_code)
        headers['Origin'] = 'http://testserver'
        self.assertEqual(400, client.post(endpoint, headers=headers, json={'confirm': 1}).status_code)
        with patch('radai_queue_state.quem_tem_a_vez', return_value={'dono': None}), \
                patch('radai_queue_state.pedir_fechar_ao_fim'), patch('radai_atualizar._status', return_value={}):
            self.assertEqual(202, client.post(endpoint, headers=headers,
                json=self.confirmed_install_payload(status)).status_code)
        self.assertEqual(403, client.get('/api/plugins/neuro-rt', headers={'Host': 'external.test'}).status_code)

    def test_confirmed_install_delegates_without_claiming_download_progress(self):
        calls = []
        self.cfg['neuro_install'] = lambda: calls.append(True) or {'state': 'preparing'}
        HOST.montar(self.app, self.cfg)
        client = TestClient(self.app)
        status = client.get('/api/plugins/neuro-rt').json()
        self.assertTrue(status['install_available'])
        result = client.post('/api/plugins/neuro-rt/install', json=self.confirmed_install_payload(status),
                             headers={'X-Neuro-Plugin-Token': status['token']})
        self.assertEqual(202, result.status_code)
        self.assertEqual({'state': 'preparing'}, result.json())
        self.assertEqual([True], calls)

    def test_plugin_update_waits_while_the_base_updater_is_running(self):
        HOST.montar(self.app, self.cfg)
        client = TestClient(self.app)
        status = client.get('/api/plugins/neuro-rt').json()
        token = status['token']
        with patch('radai_atualizar.etapa', return_value='baixando'):
            result = client.post('/api/plugins/neuro-rt/install', json=self.confirmed_install_payload(status),
                headers={'X-Neuro-Plugin-Token': token})
        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.json()['state'], 'busy')

    def test_blocked_integrity_check_keeps_home_and_neuro_responsive_and_mounts_once(self):
        self.ready()
        self.app.get('/')(lambda: {'home': True})
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = HOST.discover_plugin
        calls = []
        def blocked(*args, **kwargs):
            calls.append(True)
            entered.set()
            release.wait(3)
            return original(*args, **kwargs)
        with patch.object(HOST, 'discover_plugin', side_effect=blocked):
            start = time.perf_counter()
            entry = HOST.montar(self.app, self.cfg)
            self.assertLess(time.perf_counter() - start, 1.5)
            self.assertEqual(self.app.calls, 0)
            client = TestClient(self.app)
            self.assertEqual(client.get('/').json(), {'home': True})
            with patch('radai_menu.aplicar', side_effect=lambda p, _: p):
                start = time.perf_counter()
                page = client.get('/neuro', follow_redirects=False)
                self.assertLess(time.perf_counter() - start, 1.5)
            self.assertEqual(page.status_code, 200)
            self.assertTrue(entered.wait(2))
            status = client.get('/api/plugins/neuro-rt').json()
            self.assertEqual(status['state'], 'checking')
            self.assertFalse(status['mounted'])
            self.assertEqual(len(calls), 1)
            release.set()
            self.assertTrue(entry['load_complete'].wait(10))
        self.assertEqual(self.app.calls, 1)
        self.assertTrue(client.get('/api/plugins/neuro-rt').json()['mounted'])

    def test_background_hash_failure_never_executes_payload(self):
        code = self.ready()
        (code / 'integration/adapter.py').write_text('raise AssertionError("must never execute")')
        entry = HOST.montar(self.app, self.cfg)
        self.assertEqual(self.app.calls, 0)
        self.await_load(entry)
        self.assertEqual(entry['installation']['state'], 'failed')
        self.assertFalse(entry['receipt'])

    def test_shutdown_during_integrity_check_prevents_late_mount(self):
        self.ready()
        entered = threading.Event()
        original = HOST.discover_plugin
        def blocked(*args, cancelled=None, **kwargs):
            entered.set()
            deadline = time.monotonic() + 5
            while not cancelled() and time.monotonic() < deadline:
                time.sleep(.01)
            return original(*args, cancelled=cancelled, **kwargs)
        with patch.object(HOST, 'discover_plugin', side_effect=blocked):
            entry = HOST.montar(self.app, self.cfg)
            with TestClient(self.app) as client:
                client.get('/api/plugins/neuro-rt')
                self.assertTrue(entered.wait(2))
            self.assertTrue(entry['load_complete'].wait(2))
        self.assertEqual(self.app.calls, 0)
        self.assertFalse(entry['receipt'])

    def test_slow_mount_keeps_status_responsive_while_loading(self):
        self.ready()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = HOST.build_host_services
        def slow(*args, **kwargs):
            entered.set()
            release.wait(3)
            return original(*args, **kwargs)
        with patch.object(HOST, 'build_host_services', side_effect=slow):
            entry = HOST.montar(self.app, self.cfg)
            client = TestClient(self.app)
            client.get('/api/plugins/neuro-rt')
            self.assertTrue(entered.wait(2))
            started = time.perf_counter()
            status = client.get('/api/plugins/neuro-rt').json()
            self.assertLess(time.perf_counter() - started, 1.5)
            self.assertEqual(status['state'], 'loading')
            release.set()
            self.assertTrue(entry['load_complete'].wait(10))

    def test_background_mount_waits_for_actual_queue_idle(self):
        self.ready()
        owner = {'dono': 'lote'}
        with patch('radai_queue_state.quem_tem_a_vez', return_value=owner):
            entry = HOST.montar(self.app, self.cfg)
            client = TestClient(self.app)
            client.get('/api/plugins/neuro-rt')
            deadline = time.monotonic() + 3
            while 'Aguardando' not in entry['installation'].get('reason', '') and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(client.get('/api/plugins/neuro-rt').json()['state'], 'checking')
            self.assertEqual(self.app.calls, 0)
            owner['dono'] = None
            self.assertTrue(entry['load_complete'].wait(10))
        self.assertEqual(self.app.calls, 1)

    def test_latest_network_wait_does_not_hold_installed_plugin_open(self):
        self.ready()
        from neuro_rt.plugin_update import ReleaseClient
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        calls = []
        def network(*args, **kwargs):
            calls.append(True)
            entered.set()
            release.wait(3)
            raise OSError('offline fixture')
        self.cfg['neuro_release_client'] = ReleaseClient(fetch_json=network)
        entry = HOST.montar(self.app, self.cfg)
        client = TestClient(self.app)
        client.get('/api/plugins/neuro-rt')
        self.assertTrue(entered.wait(2))
        self.assertTrue(entry['load_complete'].wait(10))
        started = time.perf_counter()
        response = client.get('/neuro', follow_redirects=False)
        self.assertLess(time.perf_counter() - started, 1.5)
        self.assertEqual(response.headers['location'], '/neuro/')
        self.assertEqual(len(calls), 1)
        release.set()

    def test_common_host_catalog_preserves_home_position_and_five_tools(self):
        import radai_menu
        import radai_modules
        import radai_porta
        import radai_breadcrumb
        self.assertEqual(('bridge', 'autocontorno', 'recon3d', 'neuro', 'elastic', 'bolus'),
                         radai_menu.MODULOS_HOME)
        self.assertEqual(5, len(radai_modules.FERRAMENTAS['neuro']))
        page = radai_modules.pagina_completa('neuro')
        for title in ('Nidus RT', 'Glioma RT', 'Metastasis RT', 'Meningioma RT', 'Anatomia RT'):
            self.assertIn(title, page)
        self.assertIn('href="/neuro"', radai_porta.cartao('neuro', 3))
        self.assertEqual(('NEURO RT', '/neuro'), radai_breadcrumb.pai('nidus_projecao'))


class HostServicesTests(unittest.TestCase):
    def test_shared_callbacks_are_preserved_and_missing_services_fail_closed(self):
        from integration.host_services import build_host_services, HostDependencyUnavailable
        resolver = lambda ticket: {'ticket': ticket}
        services = build_host_services({'version': '8.10'}, {'resolve_series_ticket': resolver})
        self.assertIs(resolver, services.resolve_series_ticket)
        self.assertEqual('auto', services.device_preference())
        with self.assertRaises(HostDependencyUnavailable):
            services.export_rtstruct({})
        with self.assertRaises(HostDependencyUnavailable):
            services.require('queue_bridge')


if __name__ == '__main__':
    unittest.main()

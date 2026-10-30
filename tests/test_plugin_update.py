"""Updater contract with synthetic releases, never production models."""
import concurrent.futures
import json
from pathlib import Path
import tempfile
import time
import unittest
from neuro_rt import plugin_update as update
from neuro_rt import install_state
from test_plugin_install import fixture_package


class ReleaseTests(unittest.TestCase):
    def test_python_contract_bounds_match_private_runtime_separation(self):
        self.assertTrue(update.python_compatible('>=3.10', (3, 14)))
        self.assertTrue(update.python_compatible('>=3.10,<3.13', (3, 10)))
        self.assertTrue(update.python_compatible('>=3.10,<3.13', (3, 12)))
        self.assertFalse(update.python_compatible('>=3.10,<3.13', (3, 9)))
        self.assertFalse(update.python_compatible('>=3.10,<3.13', (3, 14)))

    def test_concurrent_latest_is_shared_and_same_version_reported(self):
        calls = []
        def fetch(url, **kw):
            calls.append(url)
            time.sleep(.03)
            return {'tag_name': 'v1.0.0', 'assets': [{'id': 7, 'name': 'NEURO_RT_OFFLINE_v1.0.0.zip',
                    'url': 'https://api.github.com/assets/7', 'size': 20, 'digest': 'sha256:' + 'a'*64}]}
        client = update.ReleaseClient(fetch_json=fetch)
        with concurrent.futures.ThreadPoolExecutor(6) as pool:
            results = list(pool.map(lambda _: client.check_plugin_release('neuro-rt', '1.0.0'), range(6)))
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(r['state'] == 'current' for r in results))

    def test_network_failure_has_no_installation_side_effect(self):
        def offline(*args, **kw):
            raise OSError('offline')
        result = update.ReleaseClient(fetch_json=offline).check_plugin_release('neuro-rt', '1.0.0')
        self.assertEqual(result['state'], 'unavailable')
        self.assertEqual(result['installed_version'], '1.0.0')

    def test_digest_required_and_private_404_is_explicit(self):
        def fetch(*args, **kw):
            raise update.ReleaseUnavailable('GitHub 404: repositório privado ou release não publicada.')
        r = update.ReleaseClient(fetch_json=fetch).check_plugin_release('neuro-rt', None)
        self.assertIn('404', r['reason'])

    def test_latest_incompatible_release_is_visible_before_download(self):
        raw = {'tag_name': 'v2.0.0', 'assets': [
            {'id': 7, 'name': 'NEURO_RT_OFFLINE_v2.0.0.zip', 'url': 'https://api.github.com/assets/7',
             'size': 20, 'digest': 'sha256:' + 'a'*64},
            {'id': 8, 'name': 'release-manifest.json', 'url': 'https://api.github.com/assets/8'}]}
        client = update.ReleaseClient(fetch_json=lambda _: raw, host_version='8.10',
            fetch_manifest=lambda _: {'schema': install_state.SCHEMA, 'version': '2.0.0', 'host_min_version': '9.0'})
        self.assertEqual(client.check_plugin_release('neuro-rt', '1.0.0')['state'], 'incompatible')


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.host = self.root / 'Suíte sintética á'
        self.host.mkdir()
        for name in ('radai_panel.py', 'radai_ui.py', 'entrega.txt'):
            (self.host / name).write_text('synthetic')
        self.plugin = self.host / 'Plugins/NEURO RT'
        self.events = []
        self.busy = False
        self.coordinator = update.UpdateCoordinator(self.host, host_version='8.10',
            hold=lambda held: self.events.append(('hold', held)), busy=lambda: self.busy,
            cancel=lambda: self.events.append(('cancel', True)),
            restart=lambda: (self.events.append(('restart', True)) or {'ok': True, 'scheduled': True}))

    def test_offline_install_and_update_preserve_old_code_data_and_hold_before_restart(self):
        for version in ('1.0.0', '2.0.0'):
            self.events.clear()
            package = fixture_package(self.root, version)
            result = self.coordinator.prepare(package)
            self.assertEqual(result['state'], 'installed_pending_restart')
            self.assertFalse(any(e[0] == 'restart' for e in self.events))
            self.coordinator.finish_restart()
            (self.plugin / 'data/keep.txt').write_text('preserve')
        self.assertTrue((self.plugin / 'versions/1.0.0/module.json').is_file())
        self.assertEqual((self.plugin / 'data/keep.txt').read_text(), 'preserve')
        self.assertEqual(self.events[-2:], [('hold', True), ('restart', True)])
        state = json.loads((self.plugin / 'installation.json').read_text())
        self.assertEqual((state['active_version'], state['previous_version']), ('2.0.0', '1.0.0'))

    def test_busy_never_activates_and_cancel_is_scoped(self):
        self.coordinator.prepare(fixture_package(self.root))
        self.busy = True
        self.assertEqual(self.coordinator.finish_restart()['state'], 'waiting')
        self.assertIsNone(json.loads((self.plugin / 'installation.json').read_text())['active_version'])
        self.coordinator.request_plugin_update('neuro-rt', 'interromper')
        self.assertIn(('cancel', True), self.events)

    def test_incompatible_package_refused_before_installation(self):
        def mutate(manifest, files):
            module = json.loads(files['code/module.json'])
            module['host_min_version'] = '99.0'
            files['code/module.json'] = json.dumps(module).encode()
            import hashlib
            for entry in manifest['files']:
                if entry['path'] == 'code/module.json':
                    entry.update(size=len(files[entry['path']]), sha256=hashlib.sha256(files[entry['path']]).hexdigest())
        package = fixture_package(self.root, mutate=mutate)
        with self.assertRaisesRegex(ValueError, 'Local Suite'):
            self.coordinator.prepare(package)
        self.assertFalse((self.plugin / 'installation.json').exists())

    def test_restart_rejection_restores_previous_pointer(self):
        self.coordinator.prepare(fixture_package(self.root))
        self.coordinator.finish_restart()
        self.coordinator.prepare(fixture_package(self.root, '2.0.0'))
        self.coordinator.restart = lambda: (_ for _ in ()).throw(OSError('restart failed'))
        result = self.coordinator.finish_restart()
        self.assertEqual(result['state'], 'installed_pending_restart')
        self.assertEqual(result['error_code'], 'RESTART_NOT_CONFIRMED')
        state = json.loads((self.plugin / 'installation.json').read_text())
        self.assertEqual(state['active_version'], '1.0.0')
        self.assertEqual(state['pending_version'], '2.0.0')

    def test_download_verify_install_activate_uses_one_pinned_release(self):
        import io
        package = fixture_package(self.root)
        raw = Path(package['path']).read_bytes()
        calls = []
        def latest(url):
            calls.append(url)
            return {'tag_name': 'v1.0.0', 'id': 42, 'assets': [{'id': 7,
                'name': 'NEURO_RT_OFFLINE_v1.0.0.zip', 'url': 'https://api.github.com/assets/7',
                'size': len(raw), 'digest': 'sha256:' + package['sha256']}]}
        self.coordinator.client = update.ReleaseClient(fetch_json=latest)
        with unittest.mock.patch.object(update, '_open', return_value=io.BytesIO(raw)):
            self.coordinator.request_plugin_update('neuro-rt', 'comecar')
            self.coordinator._worker.join(120)
            self.assertFalse(self.coordinator._worker.is_alive(), 'fixture install did not finish')
        self.assertEqual(self.coordinator.status()['state'], 'restarting')
        self.assertEqual(len(calls), 1)
        self.assertEqual(json.loads((self.plugin / 'installation.json').read_text())['active_version'], '1.0.0')

    def test_concurrent_offline_requests_share_one_real_install(self):
        self.coordinator.offline_package = fixture_package(self.root)
        self.coordinator.client = update.ReleaseClient(fetch_json=lambda _: (_ for _ in ()).throw(OSError('offline fixture')))
        self.coordinator.request_plugin_update('neuro-rt', 'comecar')
        self.coordinator.request_plugin_update('neuro-rt', 'comecar')
        self.coordinator._worker.join(120)
        self.assertFalse(self.coordinator._worker.is_alive(), 'offline fixture install did not finish')
        self.assertEqual(self.coordinator.status()['state'], 'restarting')
        self.assertEqual(len(list((self.plugin / 'transactions').iterdir())), 1)

    def test_failed_download_never_removes_a_preexisting_partial_file(self):
        from unittest.mock import patch
        target = self.root / 'transfer.zip'
        partial = target.with_suffix('.part')
        partial.write_bytes(b'preserve preexisting partial')
        release = {'url': 'https://api.github.com/assets/7', 'size': 1, 'sha256': 'a'*64}
        with patch.object(update, '_open', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.coordinator.client.download(release, target)
        self.assertEqual(partial.read_bytes(), b'preserve preexisting partial')

    def test_interrupted_download_preserves_active_installation_and_releases_queue(self):
        import io
        from unittest.mock import patch
        self.coordinator.prepare(fixture_package(self.root))
        self.coordinator.finish_restart()
        (self.plugin / 'data/keep.txt').write_bytes(b'preserve synthetic result')
        package = fixture_package(self.root, '2.0.0')
        raw = Path(package['path']).read_bytes()
        latest = {'tag_name': 'v2.0.0', 'assets': [{'id': 8,
            'name': 'NEURO_RT_OFFLINE_v2.0.0.zip', 'url': 'https://api.github.com/assets/8',
            'size': len(raw), 'digest': 'sha256:' + package['sha256']}]}
        self.coordinator.client = update.ReleaseClient(fetch_json=lambda _: latest)
        with patch.object(update, '_open', return_value=io.BytesIO(raw[:20])):
            self.coordinator.request_plugin_update('neuro-rt', 'comecar')
            self.coordinator._worker.join(120)
            self.assertFalse(self.coordinator._worker.is_alive())
        self.assertEqual(self.coordinator.status()['state'], 'failed')
        self.assertEqual(json.loads((self.plugin / 'installation.json').read_text())['active_version'], '1.0.0')
        self.assertEqual((self.plugin / 'data/keep.txt').read_bytes(), b'preserve synthetic result')
        self.assertEqual(self.events[-1], ('hold', False))

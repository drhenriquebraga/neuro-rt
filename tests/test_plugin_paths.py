import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from neuro_rt import plugin_paths
from neuro_rt.service import Service, Settings


class PluginPathsTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parents[1] / '.research' / 'test_plugin_tmp'
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='neuro paths ', dir=temp_root)
        self.addCleanup(self.temp.cleanup)
        self.host = Path(self.temp.name).resolve() / 'Suíte com espaço'
        self.state = {'state': 'ready', 'active_version': '0.2.0',
                      'runtime': {'id': 'raidionics-cpu', 'lock_digest': 'a' * 64,
                                  'python': 'python.exe'}}

    def test_resolves_separate_code_runtime_models_data_without_creating_directories(self):
        paths = plugin_paths.resolve_plugin_paths(self.host, self.state)
        root = self.host / 'Plugins' / 'NEURO RT'
        self.assertEqual(paths.host_root, self.host)
        self.assertEqual(paths.plugin_root, root)
        self.assertEqual(paths.code_dir, root / 'versions' / '0.2.0')
        self.assertEqual(paths.models_dir, root / 'models')
        self.assertEqual(paths.data_dir, root / 'data')
        self.assertEqual(paths.config_dir, root / 'config')
        self.assertEqual(paths.installation_file, root / 'installation.json')
        self.assertEqual(paths.staging_dir, root / 'staging')
        self.assertEqual(paths.runtime_dir, root / 'runtimes' / 'raidionics-cpu' / ('a' * 64))
        self.assertEqual(paths.worker_python, paths.runtime_dir / 'python.exe')
        self.assertFalse(self.host.exists())

    def test_absent_installation_has_no_active_code_or_runtime(self):
        paths = plugin_paths.resolve_plugin_paths(self.host, None)
        self.assertEqual(paths.state.value, 'absent')
        self.assertIsNone(paths.code_dir)
        self.assertIsNone(paths.worker_python)
        self.assertFalse(self.host.exists())

    def test_public_installation_states_can_resolve_independently_of_models(self):
        for state in ('absent', 'checking', 'installing', 'installed_pending_restart',
                      'ready', 'updating', 'incompatible', 'failed'):
            with self.subTest(state=state):
                values = dict(self.state, state=state)
                paths = plugin_paths.resolve_plugin_paths(self.host, values)
                self.assertEqual(paths.state.value, state)
        with self.assertRaises(ValueError):
            plugin_paths.resolve_plugin_paths(self.host, dict(self.state, state='model_missing'))

    def test_rejects_path_injections_without_creating_destination(self):
        for version in ('../outside', '..\\outside', '/absolute', 'C:/outside', 'C:outside', '', True):
            with self.subTest(version=version), self.assertRaises(ValueError):
                plugin_paths.resolve_plugin_paths(self.host, dict(self.state, active_version=version))
        for runtime in ({'id': '../outside', 'lock_digest': 'a' * 64},
                        {'id': 'cpu', 'lock_digest': '../outside'},
                        {'id': 'cpu', 'lock_digest': 'a' * 64, 'python': '../outside.exe'},
                        {'id': 'cpu', 'lock_digest': 'a' * 64, 'python': 'python.exe:stream'}):
            with self.subTest(runtime=runtime), self.assertRaises(ValueError):
                plugin_paths.resolve_plugin_paths(self.host, dict(self.state, runtime=runtime))
        self.assertFalse(self.host.exists())

    def test_rejects_symlinked_plugin_or_storage_outside_its_boundary(self):
        with tempfile.TemporaryDirectory(dir=Path(self.temp.name).parent) as outside:
            root = self.host / 'Plugins' / 'NEURO RT'
            root.mkdir(parents=True)
            for link in (root / 'data', root / 'versions', root / 'runtimes', root / 'models'):
                try:
                    link.symlink_to(outside, target_is_directory=True)
                except OSError as error:
                    self.skipTest(f'Sistema não permite symlinks: {error}')
                try:
                    with self.subTest(link=link), self.assertRaises(ValueError):
                        plugin_paths.resolve_plugin_paths(self.host, self.state)
                finally:
                    link.unlink()

    def test_development_settings_preserve_defaults_and_explicit_local_paths(self):
        self.host.mkdir()
        settings = Settings(self.host)
        self.assertEqual(settings.root, self.host)
        self.assertEqual(settings.models_dir, self.host / 'models')
        self.assertEqual(settings.data_dir, self.host / 'runtime')
        self.assertEqual(settings.host_app, self.host / 'host-app')
        self.assertEqual(settings.host_python, str(self.host / 'host-python.exe'))
        self.assertEqual(settings.python, sys.executable)
        (self.host / 'neuro_rt.local.json').write_text(json.dumps({
            'worker_python': 'dev python/python.exe', 'models_dir': 'weights',
            'data_dir': 'jobs', 'host_app': '../host', 'host_python': sys.executable,
        }), encoding='utf-8')
        configured = Settings(self.host)
        self.assertEqual(configured.python, str(self.host / 'dev python' / 'python.exe'))
        self.assertEqual(configured.models_dir, self.host / 'weights')
        self.assertEqual(configured.data_dir, self.host / 'jobs')
        self.assertEqual(configured.host_app, self.host.parent / 'host')
        self.assertEqual(configured.host_python, sys.executable)

    def test_production_without_runtime_reports_incomplete_and_never_uses_host_python(self):
        paths = plugin_paths.resolve_plugin_paths(self.host, self.state)
        settings = Settings(paths.code_dir, plugin_paths=paths)
        self.assertEqual(settings.python, str(paths.worker_python))
        self.assertNotEqual(settings.python, sys.executable)
        status = Service(settings).status()
        self.assertFalse(status['runtime_ready'])
        self.assertEqual(status['installation_state'], 'failed')
        self.assertTrue(status['installation_reason'])
        self.assertFalse(self.host.exists())

    def test_production_ready_runtime_uses_split_paths_and_host_exporter(self):
        paths = plugin_paths.resolve_plugin_paths(self.host, self.state)
        paths.worker_python.parent.mkdir(parents=True)
        paths.worker_python.touch()
        settings = Settings(paths.code_dir, plugin_paths=paths)
        self.assertEqual(settings.root, paths.code_dir)
        self.assertEqual(settings.models_dir, paths.models_dir)
        self.assertEqual(settings.data_dir, paths.data_dir)
        self.assertEqual(settings.host_app, self.host)
        self.assertEqual(settings.host_python, str(self.host / 'python' / 'python.exe'))
        status = Service(settings).status()
        self.assertTrue(status['runtime_ready'])
        self.assertEqual(status['installation_state'], 'ready')

    def test_production_with_no_selected_runtime_has_no_fallback(self):
        paths = plugin_paths.resolve_plugin_paths(self.host, dict(self.state, runtime=None))
        settings = Settings(paths.code_dir, plugin_paths=paths)
        self.assertIsNone(settings.python)
        self.assertFalse(settings.runtime_ready)
        self.assertEqual(settings.installation_state, 'failed')

    def test_production_does_not_load_development_config_from_version(self):
        paths = plugin_paths.resolve_plugin_paths(self.host, self.state)
        paths.code_dir.mkdir(parents=True)
        (paths.code_dir / 'neuro_rt.local.json').write_text(json.dumps({
            'worker_python': sys.executable, 'data_dir': '../outside',
        }), encoding='utf-8')
        settings = Settings(paths.code_dir, plugin_paths=paths)
        self.assertEqual(settings.python, str(paths.worker_python))
        self.assertEqual(settings.data_dir, paths.data_dir)

    def test_production_without_runtime_rejects_submission_before_creating_job(self):
        paths = plugin_paths.resolve_plugin_paths(self.host, self.state)
        service = Service(Settings(paths.code_dir, plugin_paths=paths))
        with self.assertRaisesRegex(ValueError, 'runtime'):
            service.submit({'model': 'MRI_GBM', 'input_path': str(self.host),
                            'explicit_request': True})
        self.assertFalse(self.host.exists())

    def test_rejects_junctioned_plugin_root_outside_host_on_windows(self):
        if sys.platform != 'win32':
            self.skipTest('Junctions são específicos do Windows.')
        with tempfile.TemporaryDirectory(dir=Path(self.temp.name).parent) as outside:
            parent = self.host / 'Plugins'
            parent.mkdir(parents=True)
            link = parent / 'NEURO RT'
            creation = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), outside],
                                      capture_output=True, text=True)
            self.assertEqual(creation.returncode, 0, creation.stderr)
            try:
                with self.assertRaises(ValueError):
                    plugin_paths.resolve_plugin_paths(self.host, self.state)
            finally:
                link.rmdir()


if __name__ == '__main__':
    unittest.main()

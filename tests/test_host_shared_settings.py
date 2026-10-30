import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from neuro_rt import plugin_manifest, plugin_paths
from neuro_rt.service import Service, Settings


class HostSharedSettingsTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.module = {'schema': 'neuro-rt/plugin-manifest/1', 'id': 'neuro-rt',
            'version': '1.0.2', 'host_contract': 'local-suite/plugins/1', 'host_min_version': '8.11',
            'entrypoint': '/neuro/', 'adapter': 'integration/radai_neuro.py:montar',
            'catalog': 'catalog/models.json', 'execution_mode': 'host', 'runtime': 'host-shared',
            'runtimes': {}, 'enabled_tools': ['nidus'], 'artifacts': []}
        self.state = {'state': 'ready', 'active_version': '1.0.2', 'execution_mode': 'host', 'runtime': None}

    def manifest(self, **changes):
        value = dict(self.module, **changes)
        path = self.root / 'module.json'
        path.write_text(json.dumps(value), encoding='utf-8')
        return plugin_manifest.read_manifest(path)

    def test_host_manifest_accepts_only_the_closed_nidus_profile(self):
        try:
            manifest = self.manifest()
        except ValueError as error:
            self.fail('The explicit host/Nidus profile must be accepted: ' + str(error))
        self.assertEqual(manifest.execution_mode, 'host')
        self.assertEqual(manifest.enabled_tools, ('nidus',))
        self.assertEqual(manifest.runtimes, {})
        self.assertEqual(manifest.artifacts, ())

    def test_host_manifest_refuses_private_runtime_future_tools_and_payload(self):
        for changes in ({'runtime': 'isolated-worker'}, {'runtime': None},
                        {'runtimes': {'private': {'python': 'python.exe'}}},
                        {'enabled_tools': ['nidus', 'glioma']}, {'enabled_tools': []},
                        {'enabled_tools': 'nidus'}, {'artifacts': [{'path': 'weights.bin'}]},
                        {'execution_mode': 'unknown'}, {'execution_mode': 'isolated'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.manifest(**changes)

    def test_legacy_manifest_defaults_are_preserved(self):
        self.module.pop('execution_mode')
        self.module.pop('enabled_tools')
        manifest = self.manifest(runtime='isolated-worker', runtimes={'old': {'python': 'python.exe'}})
        self.assertEqual(manifest.execution_mode, 'isolated')
        self.assertEqual(manifest.enabled_tools, ())

    def test_host_module_refuses_interpreter_paths_in_recipe(self):
        for key in ('host_python', 'python_executable', 'worker_python'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.manifest(**{key: 'C:/untrusted/python.exe'})

    @patch('importlib.metadata.version', return_value='1.0')
    def test_host_binding_returns_same_executable_without_scientific_imports(self, metadata):
        self.assertTrue(hasattr(plugin_manifest, 'validate_host_runtime'))
        before = set(sys.modules)
        binding = plugin_manifest.validate_host_runtime(sys.executable)
        self.assertEqual(binding, Path(sys.executable).resolve())
        self.assertEqual(set(call.args[0] for call in metadata.call_args_list),
                         {'numpy', 'SimpleITK', 'scipy', 'pydicom', 'fastapi', 'Pillow'})
        self.assertFalse(any(name.split('.')[0] in {'numpy', 'scipy', 'SimpleITK', 'torch',
            'onnxruntime', 'pydicom', 'PIL', 'fastapi'} for name in set(sys.modules) - before))

    @patch('importlib.metadata.version', return_value='1.0')
    def test_host_binding_is_mandatory_absolute_and_cannot_select_another_python(self, metadata):
        self.assertTrue(hasattr(plugin_manifest, 'validate_host_runtime'))
        other = self.root / 'other-python.exe'
        other.touch()
        for value in (None, '', 'python.exe', Path('relative/python.exe'), other, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                plugin_manifest.validate_host_runtime(value)
        metadata.assert_not_called()

    @patch('importlib.metadata.version', side_effect=importlib.metadata.PackageNotFoundError('missing'))
    def test_missing_base_dependency_fails_without_pip_or_raw_paths(self, metadata):
        self.assertTrue(hasattr(plugin_manifest, 'validate_host_runtime'))
        with self.assertRaisesRegex(ValueError, 'base') as error:
            plugin_manifest.validate_host_runtime(sys.executable)
        self.assertNotIn(str(self.root), str(error.exception))

    @patch('importlib.metadata.version', return_value='')
    def test_empty_base_metadata_is_not_a_ready_dependency(self, metadata):
        with self.assertRaisesRegex(ValueError, 'base'):
            plugin_manifest.validate_host_runtime(sys.executable)

    @patch('importlib.metadata.version', return_value='1.0')
    def test_host_python_older_than_310_is_rejected(self, metadata):
        self.assertTrue(hasattr(plugin_manifest, 'validate_host_runtime'))
        with patch.object(plugin_manifest.sys, 'version_info', (3, 9)):
            with self.assertRaisesRegex(ValueError, '3.10'):
                plugin_manifest.validate_host_runtime(sys.executable)
        metadata.assert_not_called()

    @patch('importlib.metadata.version', return_value='1.0')
    def test_shared_paths_settings_ready_and_empty_future_delta(self, metadata):
        paths = plugin_paths.resolve_plugin_paths(self.root, self.state, host_python=sys.executable)
        self.assertEqual(paths.execution_mode, 'host')
        self.assertIsNone(paths.runtime_dir)
        self.assertEqual(paths.worker_python, Path(sys.executable).resolve())
        settings = Settings(paths.code_dir, plugin_paths=paths)
        self.assertEqual(settings.python, str(Path(sys.executable).resolve()))
        self.assertEqual(settings.host_python, settings.python)
        self.assertTrue(settings.runtime_ready)
        self.assertEqual(settings.installation_state, 'ready')
        self.assertEqual(Service(settings).status()['installation_state'], 'ready')
        for runtime_id in ('raidionics-onnx', 'neuro-scientific-cpu', 'host-nnunet', 'unknown'):
            self.assertIsNone(settings.runtime_python(runtime_id))
        self.assertFalse((self.root / 'Plugins').exists())

    @patch('importlib.metadata.version', return_value='1.0')
    def test_installed_state_never_supplies_the_interpreter_or_private_runtime(self, metadata):
        for changes in ({'host_python': sys.executable}, {'python_executable': sys.executable},
                        {'runtime': {'id': 'private', 'lock_digest': 'a' * 64, 'python': 'python.exe'}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                plugin_paths.resolve_plugin_paths(self.root, dict(self.state, **changes))
        with self.assertRaises(ValueError):
            plugin_paths.resolve_plugin_paths(self.root, dict(self.state, runtime={'python': 'python.exe'}), host_python=sys.executable)
        for key in ('host_python', 'python_executable', 'worker_python'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                plugin_paths.resolve_plugin_paths(self.root, dict(self.state, **{key: str(self.root / 'untrusted.exe')}), host_python=sys.executable)

    @unittest.skipUnless(importlib.util.find_spec('fastapi'), 'FastAPI pertence à base do host.')
    @patch('importlib.metadata.version', return_value='1.0')
    def test_adapter_preserves_the_trusted_host_interpreter(self, metadata):
        from fastapi import FastAPI
        from integration.radai_neuro import montar
        plugin = self.root / 'Plugins/NEURO RT'
        code = plugin / 'versions/1.0.2'
        (code / 'web').mkdir(parents=True)
        (plugin / 'installation.json').write_text(json.dumps(self.state), encoding='utf-8')
        host = SimpleNamespace(host_info={'suite_root': str(self.root), 'python_executable': sys.executable})
        service = SimpleNamespace(token='synthetic-token', close=lambda: None)
        with patch('neuro_rt.service.Service', return_value=service) as create, \
                patch('integration.nidus_bridge.montar'):
            self.assertIs(montar(FastAPI(), code, host_services=host), service)
        settings = create.call_args.args[0]
        self.assertEqual(settings.python, str(Path(sys.executable).resolve()))
        self.assertEqual(settings.host_python, settings.python)
        self.assertTrue(settings.runtime_ready)


if __name__ == '__main__':
    unittest.main()

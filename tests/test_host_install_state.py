"""Tiny host-shared SETUP transactions; no scientific imports or installations."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from host_setup_fixtures import host_setup
from test_plugin_install import fixture_package
from neuro_rt import install_state as installer


class HostInstallStateTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='host code ', dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.host = self.root / 'Suite synthetique'
        self.host.mkdir()
        for name in ('radai_panel.py', 'radai_ui.py', 'entrega.txt'):
            (self.host / name).write_text('synthetic host marker', encoding='utf-8')
        self.plugin = self.host / 'Plugins/NEURO RT'
        self.python = Path(sys.executable).resolve()
        self.preflight = patch.object(installer, 'validate_host_runtime',
                                     return_value=self.python, create=True)
        self.validate = self.preflight.start()
        self.addCleanup(self.preflight.stop)

    def install(self, transaction='host1', **kwargs):
        return installer.begin_install(self.host, host_setup(self.root, **kwargs),
                                       transaction, host_python=self.python)

    def state(self):
        return json.loads((self.plugin / 'installation.json').read_text(encoding='utf-8'))

    def test_code_only_setup_preserves_mode_without_private_runtime_or_python_path(self):
        def include_installer(_manifest, files):
            files['code/installer/INSTALL.ps1'] = b'Write-Output "Synthetic phase"\n'
        receipt = self.install(mutate=include_installer)
        self.assertTrue(receipt.activation_pending)
        pending = self.state()
        self.assertEqual(pending['pending_execution_mode'], 'host')
        self.assertIsNone(pending['pending_runtime'])
        self.assertNotIn(str(self.python), json.dumps(pending))
        self.assertEqual(list((self.plugin / 'runtimes').glob('*')), [])
        self.assertEqual(list((self.plugin / 'models').glob('*')), [])
        self.assertTrue((self.plugin / 'versions/1.0.2/installer/INSTALL.ps1').is_file())
        installer.activate_release(self.plugin, '1.0.2', host_python=self.python)
        active = self.state()
        self.assertEqual(active['execution_mode'], 'host')
        self.assertIsNone(active['runtime'])
        self.assertIsNone(active['pending_execution_mode'])
        self.assertIsNone(active['pending_version'])
        self.assertNotIn(str(self.python), json.dumps(active))
        self.assertEqual(installer.read_install_status(self.plugin).state, 'ready')
        self.assertEqual(self.validate.call_args_list[0].args, (self.python,))
        self.assertEqual(self.validate.call_args_list[-1].args, (self.python,))

    def test_repeating_transaction_still_validates_the_current_host_binding(self):
        package = host_setup(self.root)
        first = installer.begin_install(self.host, package, 'repeat', host_python=self.python)
        self.validate.reset_mock()
        self.assertEqual(installer.begin_install(self.host, package, 'repeat',
                                                host_python=self.python), first)
        self.validate.assert_called_once_with(self.python)

    def test_missing_binding_and_incomplete_base_never_promote_or_change_active_pointer(self):
        self.install(transaction='existing')
        installer.activate_release(self.plugin, '1.0.2', host_python=self.python)
        (self.plugin / 'data/keep.txt').write_bytes(b'preserved synthetic data')
        before = (self.plugin / 'installation.json').read_bytes()
        package = host_setup(self.root, '1.0.3')
        for transaction, binding, reason in (
            ('missingbinding', None, 'Binding do Python da suite ausente.'),
            ('incompletebase', self.python, 'Dependencia obrigatoria da base ausente.'),
        ):
            self.validate.side_effect = ValueError(reason)
            with self.subTest(transaction=transaction), self.assertRaisesRegex(ValueError, reason):
                installer.begin_install(self.host, package, transaction, host_python=binding)
            self.assertFalse((self.plugin / 'versions/1.0.3').exists())
            self.assertEqual((self.plugin / 'installation.json').read_bytes(), before)
            self.assertEqual((self.plugin / 'data/keep.txt').read_bytes(), b'preserved synthetic data')

    def test_activation_preflight_failure_preserves_pending_pointer(self):
        self.install()
        before = (self.plugin / 'installation.json').read_bytes()
        self.validate.side_effect = ValueError('Base incompleta.')
        with self.assertRaisesRegex(ValueError, 'Base incompleta'):
            installer.activate_release(self.plugin, '1.0.2', host_python=self.python)
        self.assertEqual((self.plugin / 'installation.json').read_bytes(), before)

    def test_legacy_ignores_host_binding_and_transition_preserves_old_components(self):
        self.validate.side_effect = AssertionError('Legacy must not validate the host binding.')
        installer.begin_install(self.host, fixture_package(self.root), 'legacy', host_python='ignored')
        installer.activate_release(self.plugin, '1.0.0', host_python='ignored')
        legacy_runtime = dict(self.state()['runtime'])
        legacy_weight = self.plugin / 'models/fixture/1/model.onnx'
        before = legacy_weight.read_bytes()
        self.validate.side_effect = None
        self.install(transaction='shared')
        self.assertEqual(self.state()['execution_mode'], 'isolated')
        self.assertEqual(self.state()['runtime'], legacy_runtime)
        self.assertEqual(self.state()['pending_execution_mode'], 'host')
        installer.activate_release(self.plugin, '1.0.2', host_python=self.python)
        self.assertEqual(self.state()['execution_mode'], 'host')
        self.assertEqual(self.state()['previous_version'], '1.0.0')
        self.assertIsNone(self.state()['runtime'])
        self.assertEqual(legacy_weight.read_bytes(), before)
        self.assertTrue((self.plugin / 'versions/1.0.0/module.json').is_file())

    def test_host_release_rejects_model_runtime_payload_and_nonempty_component_lists(self):
        mutations = (
            lambda manifest, files: files.update({'models/fake/1/model.onnx': b'weight'}),
            lambda manifest, files: files.update({'runtimes/fake/' + '0' * 64 + '/python.exe': b'MZ'}),
            lambda manifest, files: manifest.update(runtime={'id': 'fake'}),
            lambda manifest, files: manifest.update(runtimes=[{'id': 'fake'}]),
            lambda manifest, files: manifest.update(models=[{'id': 'fake'}]),
        )
        for index, mutate in enumerate(mutations):
            package = host_setup(self.root, mutate=mutate)
            with self.subTest(index=index), zipfile.ZipFile(package['path']) as archive:
                with self.assertRaises(ValueError):
                    installer._inspect_zip(archive)

    def test_host_release_rejects_binaries_or_weights_hidden_under_code(self):
        for suffix in ('.exe', '.DLL', '.pyd', '.whl', '.onnx', '.pt', '.pth',
                       '.nii', '.nii.gz', '.dcm', '.dicom', '.h5', '.npz', '.bin'):
            def mutate(_manifest, files, suffix=suffix):
                files['code/web/hidden' + suffix] = b'synthetic forbidden payload'
            package = host_setup(self.root, mutate=mutate)
            with self.subTest(suffix=suffix), zipfile.ZipFile(package['path']) as archive:
                with self.assertRaises(ValueError):
                    installer._inspect_zip(archive)

    def test_host_release_rejects_binary_content_renamed_as_source(self):
        def mutate(_manifest, files):
            files['code/integration/disguised.py'] = b'MZ\x00\x01synthetic binary'
        package = host_setup(self.root, mutate=mutate)
        with zipfile.ZipFile(package['path']) as archive, self.assertRaises(ValueError):
            installer._inspect_zip(archive)

    def test_host_catalog_keeps_future_specs_without_claiming_their_weights(self):
        real_catalog = Path(__file__).resolve().parents[1] / 'catalog/models.json'
        def mutate(_manifest, files):
            files['code/catalog/models.json'] = real_catalog.read_bytes()
        self.assertTrue(self.install(mutate=mutate).activation_pending)

    def test_host_catalog_is_still_validated_and_only_nidus_can_be_enabled(self):
        for index, tools in enumerate((['nidus', 'glioma'], ['anatomia'])):
            def mutate(_manifest, files, tools=tools):
                module = json.loads(files['code/module.json'])
                module['enabled_tools'] = tools
                files['code/module.json'] = json.dumps(module).encode()
            with self.subTest(tools=tools), self.assertRaises(ValueError):
                self.install(transaction='tool' + str(index), mutate=mutate)
        def invalid_catalog(_manifest, files):
            files['code/catalog/models.json'] = b'{"schema":"wrong", "models":[]}'
        with self.assertRaises(ValueError):
            self.install(transaction='badcatalog', mutate=invalid_catalog)
        self.assertFalse((self.plugin / 'versions/1.0.2').exists())

    def test_module_mode_cannot_disagree_with_package(self):
        def mutate(_manifest, files):
            module = json.loads(files['code/module.json'])
            module['execution_mode'] = 'isolated'
            files['code/module.json'] = json.dumps(module).encode()
        with self.assertRaises(ValueError):
            self.install(mutate=mutate)

    def test_unknown_execution_mode_is_not_accepted_as_legacy(self):
        package = host_setup(self.root, mutate=lambda manifest, _files:
                             manifest.update(execution_mode='untrusted'))
        with zipfile.ZipFile(package['path']) as archive, self.assertRaises(ValueError):
            installer._inspect_zip(archive)

    def test_host_package_cannot_supply_a_python_binding(self):
        for key in ('host_python', 'python_executable', 'worker_python'):
            def mutate(manifest, _files, key=key):
                manifest[key] = 'C:/synthetic-untrusted/python.exe'
            package = host_setup(self.root, mutate=mutate)
            with self.subTest(key=key), zipfile.ZipFile(package['path']) as archive:
                with self.assertRaises(ValueError):
                    installer._inspect_zip(archive)
            legacy = fixture_package(self.root, mutate=mutate)
            with zipfile.ZipFile(legacy['path']) as archive:
                data, _components, _size, _entries = installer._inspect_zip(archive)
                self.assertEqual(data[key], 'C:/synthetic-untrusted/python.exe')


if __name__ == '__main__':
    unittest.main()

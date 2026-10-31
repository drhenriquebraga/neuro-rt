"""Synthetic missing extras and model assets, never another interpreter."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

try:
    from neuro_rt import resource_preparation as resources
except ImportError:
    resources = None


class ResourcePreparationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(resources, 'Host-shared resource preparation is not implemented.')
        base = Path(__file__).resolve().parents[1] / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='resources ', dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'offline'
        (self.source / 'downloads').mkdir(parents=True)
        self.plugin = self.root / 'plugin'
        self.binding = patch.object(resources, 'validate_host_runtime', return_value=Path(sys.executable))
        self.binding.start()
        self.addCleanup(self.binding.stop)
        self.base_versions = patch.object(resources, '_base_versions', return_value={'numpy': '1.26.4'})
        self.base_versions.start()
        self.addCleanup(self.base_versions.stop)
        self.recipe = {'schema': 'neuro-rt/resource-recipe/1', 'version': 'test',
                       'protected_base': {'numpy': '==1.26.4'}, 'wheels': [],
                       'downloads': {}, 'models': [], 'adapters': {}}

    def wheel(self, extra=None):
        filename = 'neuro_extra_fixture-1.0-py3-none-any.whl'
        target = self.source / 'downloads' / filename
        files = {'neuro_extra_fixture/__init__.py': b'VALUE = 17\n',
                 'neuro_extra_fixture-1.0.dist-info/METADATA':
                     b'Metadata-Version: 2.1\nName: neuro-extra-fixture\nVersion: 1.0\n',
                 'neuro_extra_fixture-1.0.dist-info/WHEEL': b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
                 'neuro_extra_fixture-1.0.dist-info/LICENSE': b'Synthetic MIT fixture license'}
        files.update(extra or {})
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, value in files.items():
                archive.writestr(name, value)
        spec = {'name': 'neuro-extra-fixture', 'version': '1.0', 'filename': filename,
                'url': 'https://files.pythonhosted.org/fixture/' + filename,
                'size': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                'license_paths': ['neuro_extra_fixture-1.0.dist-info/LICENSE'],
                'files': {name: {'size': len(value), 'sha256': hashlib.sha256(value).hexdigest(), 'member': name}
                          for name, value in files.items()}}
        self.recipe['wheels'] = [spec]
        return target

    def model(self):
        files = {}
        for filename, content in [('weight.pt', b'pinned synthetic weight'), ('LICENSE.txt', b'Synthetic MIT license')]:
            key = 'fixture-' + filename
            target = self.source / 'downloads' / key
            target.write_bytes(content)
            entry = {'filename': key, 'url': 'https://example.org/' + key,
                     'size': len(content), 'sha256': hashlib.sha256(content).hexdigest(), 'format': 'binary'}
            self.recipe['downloads'][key] = entry
            files[filename] = dict(entry, download=key)
        self.recipe['models'] = [{'id': 'fixture', 'revision': '1', 'files': files,
                                  'license_paths': ['LICENSE.txt'], 'provenance': {'model_id': 'fixture'}}]

    def prepare(self):
        return resources.prepare_resources(self.recipe, plugin_root=self.plugin,
                                            host_python=Path(sys.executable), source_folder=self.source)

    def test_offline_extras_and_models_are_verified_without_touching_base_or_network(self):
        self.wheel()
        self.model()
        with patch.object(resources.urllib.request, 'urlopen', side_effect=AssertionError('offline')):
            result = self.prepare()
        self.assertEqual(result['schema'], 'neuro-rt/resolved-resources/1')
        extra = self.plugin / result['extras_relative_path']
        self.assertTrue((extra / 'neuro_extra_fixture/__init__.py').is_file())
        self.assertTrue((extra / 'neuro_extra_fixture-1.0.dist-info/LICENSE').is_file())
        self.assertEqual((self.plugin / result['model_relative_paths']['fixture'] / 'weight.pt').read_bytes(),
                         b'pinned synthetic weight')
        receipt = self.plugin / result['receipt_relative_path']
        self.assertEqual(hashlib.sha256(receipt.read_bytes()).hexdigest(), result['receipt_sha256'])
        self.assertEqual(result['recipe_digest'], resources.canonical_digest(self.recipe))
        self.assertNotIn(str(sys.executable), receipt.read_text())
        self.assertFalse(list(self.plugin.rglob('python.exe')))
        self.assertFalse(list(self.plugin.rglob('pyvenv.cfg')))

    def test_base_distribution_is_reused_instead_of_installed_in_overlay(self):
        wheel = self.wheel()
        wheel.unlink()
        with patch.object(resources, '_base_versions', return_value={'numpy': '1.26.4', 'neuro-extra-fixture': '1.0'}):
            result = self.prepare()
        extra = self.plugin / result['extras_relative_path']
        self.assertFalse((extra / 'neuro_extra_fixture').exists())

    def test_incompatible_base_fails_before_any_plugin_write(self):
        with patch.object(resources, '_base_versions', return_value={'numpy': '2.0.0'}):
            with self.assertRaisesRegex(ValueError, 'base|Base') as caught:
                self.prepare()
        self.assertEqual(getattr(caught.exception, 'error_code', None), 'HOST_INCOMPATIBLE')
        self.assertFalse(self.plugin.exists())

    def test_wheel_cannot_escape_or_shadow_a_base_module(self):
        for index, extra in enumerate(({'../escape.py': b'unsafe'}, {'json/__init__.py': b'unsafe'})):
            self.wheel(extra)
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.prepare()
            self.assertFalse((self.root / 'escape.py').exists())
            self.assertFalse(list((self.plugin / 'extras').glob('*/site-packages/neuro_extra_fixture')))

    def test_corrupted_offline_cache_does_not_trigger_network_or_publish(self):
        path = self.wheel()
        path.write_bytes(b'corrupt')
        with patch.object(resources.urllib.request, 'urlopen', side_effect=AssertionError('offline')):
            with self.assertRaisesRegex(ValueError, 'SHA|tamanho|integridade'):
                self.prepare()
        self.assertFalse(list((self.plugin / 'extras').glob('*/site-packages/neuro_extra_fixture')))

    def test_existing_model_is_immutable_and_corruption_is_not_silently_repaired(self):
        self.model()
        result = self.prepare()
        weight = self.plugin / result['model_relative_paths']['fixture'] / 'weight.pt'
        weight.write_bytes(b'corrupt active component')
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(weight.read_bytes(), b'corrupt active component')

    def test_canonical_identity_covers_nested_pins_and_has_one_newline(self):
        first = resources.canonical_bytes({'z': ['ação'], 'a': 1})
        self.assertEqual(first, b'{"a":1,"z":["a\\u00e7\\u00e3o"]}\n')
        self.assertNotEqual(resources.canonical_digest({'wheels': [{'sha256': 'a'}]}),
                            resources.canonical_digest({'wheels': [{'sha256': 'b'}]}))

    def test_forged_local_receipt_cannot_authorize_modified_extra_source(self):
        self.wheel()
        result = self.prepare()
        filename = 'neuro_extra_fixture/__init__.py'
        source = self.plugin / result['extras_relative_path'] / filename
        source.write_bytes(b'VALUE = "tampered"\n')
        receipt_path = self.plugin / result['receipt_relative_path']
        receipt = json.loads(receipt_path.read_text())
        receipt['extra_file_inventory'][filename] = {'size': source.stat().st_size,
                                                    'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        receipt_path.write_bytes(resources.canonical_bytes(receipt))
        with self.assertRaises(ValueError):
            self.prepare()

    def test_empty_package_marker_is_a_valid_pinned_wheel_member(self):
        self.wheel({'neuro_extra_fixture/optional/__init__.py': b''})
        result = self.prepare()
        self.assertEqual((self.plugin / result['extras_relative_path'] /
                          'neuro_extra_fixture/optional/__init__.py').read_bytes(), b'')

    def test_missing_import_cannot_be_reported_as_ready_or_commit_resource_receipt(self):
        self.recipe['adapters'] = {'fixture': {'modules': ['neuro_deliberately_missing_fixture']}}
        with self.assertRaisesRegex(ValueError, 'depend|Depend|import'):
            self.prepare()
        self.assertFalse(list((self.plugin / 'resources').glob('*.json')))

    def test_incompatible_python_abi_fails_before_plugin_write(self):
        self.recipe['python_abi'] = 'cp999'
        with self.assertRaisesRegex(ValueError, 'ABI|Python'):
            self.prepare()
        self.assertFalse(self.plugin.exists())

    def test_wheel_cannot_install_python_startup_hooks(self):
        self.wheel({'fixture_startup.pth': b'import os\n'})
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.plugin.exists())

    def test_offline_export_preserves_all_original_wheels_even_if_base_has_package(self):
        original = self.wheel()
        self.assertTrue(hasattr(resources, 'prepare_offline_archives'))
        with patch.object(resources, '_base_versions', return_value={'numpy': '1.26.4', 'neuro-extra-fixture': '1.0'}), \
             patch.object(resources.urllib.request, 'urlopen', return_value=io.BytesIO(original.read_bytes())) as network:
            records = resources.prepare_offline_archives(self.recipe, plugin_root=self.plugin)
        self.assertEqual([row['filename'] for row in records], [original.name])
        self.assertEqual(resources.resource_cache_path(self.plugin, records[0]).read_bytes(), original.read_bytes())
        network.assert_called_once()
        self.assertFalse((self.plugin / 'resources').exists())

    def test_new_model_revision_with_same_download_name_reuses_only_matching_sha(self):
        self.model()
        first = self.prepare()
        old = self.plugin / first['model_relative_paths']['fixture'] / 'weight.pt'
        previous = old.read_bytes()
        updated = self.root / 'updated'
        (updated / 'downloads').mkdir(parents=True)
        for path in (self.source / 'downloads').iterdir():
            (updated / 'downloads' / path.name).write_bytes(path.read_bytes())
        new_bytes = b'new pinned revision with same original filename'
        (updated / 'downloads/fixture-weight.pt').write_bytes(new_bytes)
        entry = self.recipe['downloads']['fixture-weight.pt']
        entry.update(size=len(new_bytes), sha256=hashlib.sha256(new_bytes).hexdigest())
        self.recipe['models'][0]['revision'] = '2'
        self.recipe['models'][0]['files']['weight.pt'].update(size=entry['size'], sha256=entry['sha256'])
        second = resources.prepare_resources(self.recipe, plugin_root=self.plugin,
            host_python=Path(sys.executable), source_folder=updated)
        self.assertEqual(old.read_bytes(), previous)
        self.assertEqual((self.plugin / second['model_relative_paths']['fixture'] / 'weight.pt').read_bytes(), new_bytes)

    def test_interrupted_offline_copy_does_not_poison_a_retry(self):
        self.wheel()
        def interrupted(source, destination):
            Path(destination).write_bytes(Path(source).read_bytes()[:3])
            raise OSError('Synthetic interrupted local copy')
        with patch.object(resources.shutil, 'copyfile', side_effect=interrupted), self.assertRaises(OSError):
            self.prepare()
        result = self.prepare()
        self.assertTrue((self.plugin / result['extras_relative_path'] / 'neuro_extra_fixture/__init__.py').is_file())

    def test_missing_offline_resource_has_controlled_local_bundle_diagnostic(self):
        self.wheel().unlink()
        with patch.object(resources.urllib.request, 'urlopen', side_effect=AssertionError('offline')):
            with self.assertRaises(ValueError) as caught:
                self.prepare()
        self.assertEqual(getattr(caught.exception, 'error_code', None), 'LOCAL_RESOURCES_MISSING')


if __name__ == '__main__':
    unittest.main()

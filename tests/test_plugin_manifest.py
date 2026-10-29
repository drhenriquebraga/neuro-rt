import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from neuro_rt import plugin_manifest


class PluginManifestTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parents[1] / '.research' / 'test_plugin_tmp'
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='neuro manifesto ', dir=temp_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / 'module.json'
        self.values = {
            'schema': 'neuro-rt/plugin-manifest/1', 'id': 'neuro-rt',
            'version': '0.2.0', 'host_contract': 'local-suite/plugins/1',
            'host_min_version': '2.10', 'entrypoint': '/neuro/',
            'adapter': 'integration/radai_neuro.py:montar',
            'catalog': 'neuro_rt/catalog.py',
            'runtimes': {'raidionics': {'python': 'python.exe'}},
            'artifacts': [],
        }

    def manifest(self, **changes):
        self.values.update(changes)
        self.path.write_text(json.dumps(self.values), encoding='utf-8')
        return plugin_manifest.read_manifest(self.path)

    def test_reads_relocatable_manifest_with_spaces_and_accents(self):
        self.path = self.root / 'instalação com espaço' / 'module.json'
        self.path.parent.mkdir()
        manifest = self.manifest()
        self.assertEqual(manifest.id, 'neuro-rt')
        self.assertEqual(manifest.adapter, 'integration/radai_neuro.py:montar')
        self.assertEqual(manifest.host_min_version, '2.10')

    def test_missing_manifest_is_a_readable_validation_error(self):
        with self.assertRaisesRegex(ValueError, 'manifesto'):
            plugin_manifest.read_manifest(self.path)

    def test_rejects_invalid_json_and_non_object(self):
        for text in ('{', '[]', 'null'):
            with self.subTest(text=text):
                self.path.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError):
                    plugin_manifest.read_manifest(self.path)

    def test_rejects_wrong_id_schema_contract_and_missing_fields(self):
        baseline = dict(self.values)
        for key, value in [('id', 'other-plugin'), ('schema', 'unknown/1'),
                           ('host_contract', 'local-suite/plugins/2'),
                           ('version', None), ('catalog', None), ('runtimes', [])]:
            with self.subTest(key=key):
                self.values = dict(baseline)
                with self.assertRaises(ValueError):
                    self.manifest(**{key: value})

    def test_host_minimum_must_be_numeric_string_or_unpublished(self):
        for value in (2, True, '', 'v2.0', '2.x', '2.0-beta', ' 2.0', '٢.٠'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.manifest(host_min_version=value)
        manifest = self.manifest(host_min_version=None)
        result = plugin_manifest.check_host_compatibility(
            manifest, {'contract': 'local-suite/plugins/1', 'version': '2.10'})
        self.assertFalse(result.compatible)
        self.assertTrue(result.reason)

    def test_rejects_traversal_absolute_drive_unc_and_alternate_stream(self):
        for value in ('../escape.py', '/absolute.py', 'C:/escape.py',
                      'C:escape.py', r'\\server\share\file.py',
                      r'..\escape.py', 'nested/../../escape.py', 'file.py:stream'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.manifest(catalog=value)

    def test_rejects_escaping_adapter_runtime_and_artifact_references(self):
        for changes in (
            {'adapter': '../outside.py:montar'},
            {'adapter': 'integration/radai_neuro.py:invalid-name'},
            {'runtimes': {'raidionics': {'python': '../python.exe'}}},
            {'artifacts': [{'path': '../weights.zip'}]},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.manifest(**changes)

    def test_rejects_symlink_reference_outside_manifest_directory(self):
        with tempfile.TemporaryDirectory(dir=self.root.parent) as outside:
            link = self.root / 'external'
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError as error:
                self.skipTest(f'Sistema não permite symlinks: {error}')
            with self.assertRaises(ValueError):
                self.manifest(catalog='external/catalog.py')

    def test_compares_host_versions_numerically_and_pads_missing_components(self):
        manifest = self.manifest()
        for version, expected in [('2.9', False), ('2.10', True), ('2.10.0', True), ('3', True)]:
            with self.subTest(version=version):
                result = plugin_manifest.check_host_compatibility(
                    manifest, {'contract': 'local-suite/plugins/1', 'version': version})
                self.assertEqual(result.compatible, expected)
                self.assertEqual(result.required_contract, 'local-suite/plugins/1')
                self.assertEqual(result.required_host_version, '2.10')
                self.assertTrue(result.reason)

    def test_host_with_unknown_contract_or_version_fails_closed(self):
        manifest = self.manifest()
        for host in ({}, {'contract': 'other', 'version': '20'},
                     {'contract': 'local-suite/plugins/1', 'version': 'latest'},
                     {'contract': 'local-suite/plugins/1', 'version': 20}):
            with self.subTest(host=host):
                result = plugin_manifest.check_host_compatibility(manifest, host)
                self.assertFalse(result.compatible)
                self.assertTrue(result.reason)

    def test_repository_manifest_does_not_assert_an_unpublished_host_version(self):
        manifest = plugin_manifest.read_manifest(Path(__file__).resolve().parents[1] / 'module.json')
        self.assertEqual(manifest.host_contract, 'local-suite/plugins/1')
        self.assertIsNone(manifest.host_min_version)

    def test_rejects_junction_reference_outside_manifest_directory_on_windows(self):
        if sys.platform != 'win32':
            self.skipTest('Junctions são específicos do Windows.')
        with tempfile.TemporaryDirectory(dir=self.root.parent) as outside:
            link = self.root / 'external'
            creation = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), outside],
                                      capture_output=True, text=True)
            self.assertEqual(creation.returncode, 0, creation.stderr)
            try:
                with self.assertRaises(ValueError):
                    self.manifest(catalog='external/catalog.py')
            finally:
                link.rmdir()

    def test_metadata_contracts_import_without_site_packages(self):
        execution = subprocess.run([
            sys.executable, '-S', '-c',
            'from neuro_rt.plugin_manifest import read_manifest; '
            'from neuro_rt.plugin_paths import resolve_plugin_paths; '
            'import sys; '
            'assert not any(name in sys.modules for name in ("torch", "raidionicsseg", "ants"))',
        ], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        self.assertEqual(execution.returncode, 0, execution.stderr)


if __name__ == '__main__':
    unittest.main()

"""Public setup contains only reviewed code; no development/runtime payload."""
import base64
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts import build_web_setup as builder
from neuro_rt import install_state


class WebSetupTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / 'runtime/test-tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='web-setup-', dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.source = self.folder / 'source'
        self.source.mkdir()
        self.output = self.folder / 'output'
        self.module = {'schema': 'neuro-rt/plugin-manifest/1', 'id': 'neuro-rt',
            'version': '1.0.2', 'host_contract': 'local-suite/plugins/1',
            'host_min_version': '8.11', 'python': '>=3.10',
            'entrypoint': '/neuro/', 'adapter': 'integration/radai_neuro.py:montar',
            'catalog': 'catalog/models.json', 'execution_mode': 'host',
            'runtime': 'host-shared', 'runtimes': {}, 'artifacts': [],
            'enabled_tools': ['nidus']}
        self.write('module.json', json.dumps(self.module).encode())
        for name, raw in {
            'LICENSE': b'Synthetic MIT license fixture',
            'NOTICE': b'Attributions remain part of the plugin.',
            'licenses/NIDUS.txt': b'Synthetic Apache-2.0 license fixture',
            'requirements.txt': b'# Metadata only; never installed by the setup builder.\n',
            'models.lock.json': b'{"models":{}}',
            'neuro_rt/__init__.py': b'__version__ = "1.0.2"\n',
            'integration/radai_neuro.py': b'def montar(*a, **kw): pass\n',
            'app/radai_nidus.py': b'import radai_projection\n',
            'web/plugin-update.js': b'const version = "1.0.2";\n',
            'web/study.svg': b'<svg xmlns="http://www.w3.org/2000/svg"/>',
            'catalog/models.json': json.dumps({'schema': 'neuro-rt/catalog/1', 'models': [{
                'id': 'future_fixture', 'catalog_state': 'candidate', 'groups': ['anatomia'],
                'license': {'code': 'MIT', 'weights': 'MIT', 'sources': ['https://example.org/license']},
                'channels': [{'role': 'CT'}], 'classes': []}]}).encode(),
            'scripts/model_assets_v1_manifest.json': b'{"models":{}}',
            'installer/INSTALL.ps1': b'# Use the existing host interpreter.\n',
            'installer/UPDATE.ps1': b'# Stage reviewed plugin code.\n',
            'installer/PREPARE_LATEST.ps1': b'# Consent before setup download.\n',
        }.items():
            self.write(name, raw)

    def write(self, name, raw):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def build(self):
        return builder.build_web_setup(self.output, root=self.source)

    def test_complete_small_setup_has_only_code_and_two_identical_deterministic_assets(self):
        result = self.build()
        self.assertEqual(set(result), {'setup', 'latest', 'manifest', 'sha256'})
        self.assertEqual(result['setup'].name, 'NEURO_RT_SETUP_v1.0.2.zip')
        self.assertEqual(result['latest'].name, 'NEURO_RT_SETUP_LATEST.zip')
        self.assertEqual(set(p.name for p in self.output.iterdir()), {result['setup'].name, result['latest'].name})
        raw = result['setup'].read_bytes()
        self.assertLess(len(raw), 2 * 1024 * 1024)
        self.assertEqual(raw, result['latest'].read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), result['sha256'])
        self.assertEqual(raw, self.build()['setup'].read_bytes())
        with zipfile.ZipFile(result['setup']) as archive:
            names = set(archive.namelist())
            self.assertIn('code/neuro_rt/__init__.py', names)
            self.assertIn('code/app/radai_nidus.py', names)
            self.assertIn('code/catalog/model_assets_v1_manifest.json', names)
            self.assertIn('code/LICENSE', names)
            self.assertIn('code/licenses/NIDUS.txt', names)
            for script in ('INSTALL.ps1', 'UPDATE.ps1', 'PREPARE_LATEST.ps1'):
                self.assertIn('code/installer/' + script, names)
            self.assertTrue(all(n == 'release-manifest.json' or n.startswith('code/') for n in names))
            self.assertNotIn('setup-manifest.json', names)
            manifest = json.loads(archive.read('release-manifest.json'))
            self.assertEqual(manifest, result['manifest'])
            self.assertEqual(manifest['schema'], install_state.SCHEMA)
            self.assertEqual(manifest['execution_mode'], 'host')
            self.assertIsNone(manifest['runtime'])
            self.assertEqual(manifest['runtimes'], [])
            self.assertEqual(manifest['models'], [])
            self.assertEqual({r['path'] for r in manifest['files']}, names - {'release-manifest.json'})
            for record in manifest['files']:
                content = archive.read(record['path'])
                self.assertEqual(len(content), record['size'])
                self.assertEqual(hashlib.sha256(content).hexdigest(), record['sha256'])
            self.assertNotIn(b'OFFLINE', archive.read('release-manifest.json'))
            inspected, _, _, _ = install_state._inspect_zip(archive)
            self.assertEqual(inspected, manifest)
        self.assertLess(len(json.dumps(result['manifest'])), 20000)

    def test_unlisted_runtime_weights_private_data_and_other_scripts_never_enter(self):
        for name in ('python/python.exe', 'models/weight.onnx', 'runtime/wheel.whl',
                     'data/patient.dcm', 'web/data/private.json', 'web/.venv/module.py',
                     'web/settings.local.json', 'installer/EXTRA.ps1'):
            self.write(name, b'synthetic excluded bait')
        with zipfile.ZipFile(self.build()['setup']) as archive:
            names = archive.namelist()
            self.assertFalse(any('private' in n or 'patient' in n or '.venv' in n or '.local.' in n or 'EXTRA' in n for n in names))
            self.assertFalse(any(n.endswith(('.exe', '.whl', '.onnx', '.dcm')) for n in names))

    def test_host_mode_is_required_without_silent_conversion_of_legacy_repo(self):
        for change in ({'execution_mode': 'isolated'}, {'runtime': 'isolated-worker'},
                       {'runtimes': {'foreign': {'python': 'python.exe'}}},
                       {'enabled_tools': ['nidus', 'glioma']}, {'artifacts': ['weights.onnx']}):
            with self.subTest(change=change):
                module = dict(self.module, **change)
                self.write('module.json', json.dumps(module).encode())
                with self.assertRaises(ValueError):
                    self.build()
        self.assertFalse(self.output.exists() and list(self.output.iterdir()))

    def test_all_three_powershell_entries_and_license_are_required(self):
        for name in ('installer/INSTALL.ps1', 'installer/UPDATE.ps1',
                     'installer/PREPARE_LATEST.ps1', 'LICENSE'):
            path = self.source / name
            raw = path.read_bytes()
            path.unlink()
            with self.subTest(name=name), self.assertRaises((ValueError, FileNotFoundError)):
                self.build()
            path.write_bytes(raw)

    def test_injected_outside_source_cannot_be_read_as_public_code(self):
        outside = self.folder / 'outside.py'
        outside.write_bytes(b'outside synthetic bait')
        read_bytes = Path.read_bytes

        def guarded_read(path):
            self.assertNotEqual(path, outside, 'outside bytes must not be inspected')
            return read_bytes(path)

        with patch.object(builder, 'source_code_files', return_value={'code/neuro_rt/leak.py': outside}), \
                patch.object(Path, 'read_bytes', guarded_read):
            with self.assertRaises(ValueError):
                self.build()
        self.assertFalse(self.output.exists() and list(self.output.iterdir()))

    def test_linked_code_is_rejected_even_when_target_is_inside_source(self):
        target = self.source / 'neuro_rt/__init__.py'
        link = self.source / 'neuro_rt/linked.py'
        try:
            link.symlink_to(target)
        except OSError as error:
            if os.name != 'nt':
                self.skipTest('File symlinks are not available: ' + str(error))
            # Windows junctions do not require the symlink privilege. Force the
            # collector entry so this also works on Python versions whose rglob
            # deliberately does not descend through junctions.
            junction = self.source / 'integration/linked'
            result = subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(junction),
                                     str(target.parent)], capture_output=True)
            if result.returncode:
                self.skipTest('Windows denied synthetic symlink/junction creation')
            link = junction / '__init__.py'
        name = 'code/' + link.relative_to(self.source).as_posix()
        with patch.object(builder, 'source_code_files', return_value={name: link}):
            with self.assertRaisesRegex(ValueError, 'Links|reparse'):
                self.build()

    def test_private_or_binary_injection_cannot_override_the_allowlist(self):
        for name in ('code/web/data/private.json', 'code/neuro_rt/weights.whl',
                     'code/.aws/credentials', '../outside.py'):
            target = self.write('web/injected.json', b'{}')
            with self.subTest(name=name), patch.object(builder, 'source_code_files', return_value={name: target}):
                with self.assertRaises(ValueError):
                    self.build()
        self.write('neuro_rt/hidden.py', b'MZ\x00synthetic executable bait')
        with self.assertRaises(ValueError):
            self.build()

    def test_size_guard_leaves_no_partial_assets(self):
        raw = random.Random(20261030).randbytes(3 * 1024 * 1024 + 128 * 1024)
        self.write('web/too-large.js', b'const fixture = "' + base64.b64encode(raw) + b'";\n')
        with self.assertRaisesRegex(ValueError, '3 MiB'):
            self.build()
        self.assertFalse(self.output.exists() and list(self.output.iterdir()))


if __name__ == '__main__':
    unittest.main()

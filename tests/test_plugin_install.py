"""Synthetic offline packages only: no patient data, real models or runtimes."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from neuro_rt import install_state as installer


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fixture_package(root, version='1.0.0', mutate=None, omit=()):
    runtime_digest = digest(b'locked synthetic runtime')
    runtime = {'id': 'fixture-cpu', 'lock_digest': runtime_digest, 'python': 'python.exe'}
    model = {'id': 'fixture', 'revision': '1', 'catalog_state': 'distributed',
             'runtime_id': runtime['id'], 'groups': ['glioma'],
             'license': {'code': 'MIT', 'weights': 'MIT', 'sources': ['https://example.org/license']},
             'channels': [{'role': 'T1c'}], 'classes': [{'class_id': 'tumor'}],
             'artifacts': [{'path': 'model.onnx', 'sha256': digest(b'synthetic weight')} ]}
    module = {'schema': 'neuro-rt/plugin-manifest/1', 'id': 'neuro-rt', 'version': version,
              'host_contract': 'local-suite/plugins/1', 'host_min_version': '1.0.0',
              'entrypoint': '/neuro/', 'adapter': 'integration/radai_neuro.py:montar',
              'catalog': 'catalog/models.json', 'runtimes': {runtime['id']: {'python': 'python.exe'}},
              'artifacts': []}
    files = {'code/module.json': json.dumps(module).encode(),
             'code/catalog/models.json': json.dumps({'schema': 'neuro-rt/catalog/1', 'models': [model]}).encode(),
             'code/integration/radai_neuro.py': b'def montar(): pass\n',
             'code/licenses/MIT.txt': b'Synthetic MIT license fixture',
             f'runtimes/fixture-cpu/{runtime_digest}/python.exe': b'synthetic runtime bytes',
             f'runtimes/fixture-cpu/{runtime_digest}/LICENSE.txt': b'Synthetic Python license fixture',
             'models/fixture/1/model.onnx': b'synthetic weight',
             'models/fixture/1/LICENSE.txt': b'Synthetic MIT license fixture'}
    manifest = {'schema': 'neuro-rt/release-package/1', 'plugin_id': 'neuro-rt', 'version': version,
                'runtime': runtime, 'runtimes': [dict(runtime, license_paths=['LICENSE.txt'])],
                'models': [{'id': 'fixture', 'revision': '1', 'license_paths': ['LICENSE.txt']}],
                'code_license_paths': ['licenses/MIT.txt'],
                'files': [{'path': name, 'size': len(data), 'sha256': digest(data)}
                          for name, data in files.items()]}
    if mutate:
        mutate(manifest, files)
    archive = Path(root) / ('package-' + version + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr('release-manifest.json', json.dumps(manifest))
        for name, data in files.items():
            if not any(name.startswith(prefix) for prefix in omit):
                zipped.writestr(name, data)
    return {'path': str(archive), 'sha256': digest(archive.read_bytes())}


class PluginInstallTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parents[1] / '.research' / 'test_plugin_tmp'
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='install ', dir=temp_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.host = self.root / 'Suíte sintética com espaço'
        self.host.mkdir()
        for name in ('radai_panel.py', 'radai_ui.py', 'entrega.txt'):
            (self.host / name).write_text('synthetic host marker', encoding='utf-8')
        self.plugin = self.host / 'Plugins' / 'NEURO RT'

    def install(self, version='1.0.0', transaction='txn1', **kw):
        return installer.begin_install(self.host, fixture_package(self.root, version, **kw), transaction)

    def test_install_is_pending_then_activation_selects_split_paths(self):
        receipt = self.install()
        self.assertEqual(receipt.version, '1.0.0')
        self.assertTrue(receipt.activation_pending)
        self.assertEqual(installer.read_install_status(self.plugin).state, 'installed_pending_restart')
        state = json.loads((self.plugin / 'installation.json').read_text())
        self.assertIsNone(state['active_version'])
        activation = installer.activate_release(self.plugin, '1.0.0')
        self.assertEqual(activation.active_version, '1.0.0')
        self.assertEqual(installer.read_install_status(self.plugin).state, 'ready')
        from neuro_rt.plugin_paths import resolve_plugin_paths
        paths = resolve_plugin_paths(self.host, json.loads((self.plugin / 'installation.json').read_text()))
        self.assertEqual(paths.code_dir, self.plugin / 'versions' / '1.0.0')
        self.assertTrue(paths.worker_python.is_file())
        self.assertTrue((paths.models_dir / 'fixture' / '1' / 'model.onnx').is_file())

    def test_transaction_is_idempotent_but_cannot_change_package_identity(self):
        package = fixture_package(self.root)
        first = installer.begin_install(self.host, package, 'txn1')
        self.assertEqual(installer.begin_install(self.host, package, 'txn1'), first)
        with self.assertRaises(ValueError):
            installer.begin_install(self.host, fixture_package(self.root, '2.0.0'), 'txn1')

    def test_bad_hash_and_truncated_zip_leave_active_and_data_unchanged(self):
        self.install()
        installer.activate_release(self.plugin, '1.0.0')
        (self.plugin / 'data' / 'keep.txt').write_bytes(b'preserve')
        original = (self.plugin / 'installation.json').read_bytes()
        package = fixture_package(self.root, '2.0.0')
        for txn, corrupt in [('badsha', dict(package, sha256='0' * 64)), ('truncated', None)]:
            if corrupt is None:
                path = Path(package['path'])
                path.write_bytes(path.read_bytes()[:50])
                corrupt = dict(package, sha256=digest(path.read_bytes()))
            with self.subTest(txn=txn), self.assertRaises((ValueError, zipfile.BadZipFile)):
                installer.begin_install(self.host, corrupt, txn)
            self.assertEqual((self.plugin / 'installation.json').read_bytes(), original)
            self.assertEqual((self.plugin / 'data' / 'keep.txt').read_bytes(), b'preserve')

    def test_external_sha256_and_real_host_markers_are_required(self):
        package = fixture_package(self.root)
        with self.assertRaises(ValueError):
            installer.begin_install(self.host, package['path'], 'nohash')
        (self.host / 'radai_panel.py').unlink()
        with self.assertRaises(ValueError):
            installer.begin_install(self.host, package, 'badhost')
        self.assertFalse(self.plugin.exists())

    def test_unsafe_zip_entries_and_links_are_rejected(self):
        for index, name in enumerate(('../outside', '/absolute', 'C:/escape', 'code/CON.txt',
                                      'code/a:stream', 'code/a/../../escape', 'code/a.', 'code/AUX')):
            package = fixture_package(self.root, '2.0.0')
            with zipfile.ZipFile(package['path'], 'a') as zipped:
                zipped.writestr(name, b'evil')
            package['sha256'] = digest(Path(package['path']).read_bytes())
            with self.subTest(name=name), self.assertRaises(ValueError):
                installer.begin_install(self.host, package, 'unsafe' + str(index))
        package = fixture_package(self.root, '2.0.0')
        with zipfile.ZipFile(package['path'], 'a') as zipped:
            link = zipfile.ZipInfo('code/link')
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            zipped.writestr(link, '../outside')
        package['sha256'] = digest(Path(package['path']).read_bytes())
        with self.assertRaises(ValueError):
            installer.begin_install(self.host, package, 'link')
        self.assertFalse((self.root / 'outside').exists())

    def test_disk_shortage_and_cancelled_copy_never_publish_release(self):
        package = fixture_package(self.root)
        with patch.object(installer.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(1, 1, 0)):
            with self.assertRaisesRegex(ValueError, 'espaço'):
                installer.begin_install(self.host, package, 'full')
        with patch.object(installer, '_copy_stream', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                installer.begin_install(self.host, package, 'cancel')
        self.assertFalse((self.plugin / 'versions' / '1.0.0').exists())
        self.assertEqual(installer.read_install_status(self.plugin).state, 'failed')
        self.assertTrue(self.install(transaction='recover').activation_pending)

    def test_exclusive_lock_makes_second_request_follow_current_transaction(self):
        self.plugin.mkdir(parents=True)
        with installer._installation_lock(self.plugin) as acquired:
            self.assertTrue(acquired)
            result = installer.begin_install(self.host, fixture_package(self.root), 'other')
            self.assertTrue(result.following)
        self.assertFalse((self.plugin / 'versions').exists())

    def test_reuses_verified_components_and_keeps_previous_version_for_rollback(self):
        self.install()
        installer.activate_release(self.plugin, '1.0.0')
        weight = self.plugin / 'models' / 'fixture' / '1' / 'model.onnx'
        modified = weight.stat().st_mtime_ns
        second = self.install('2.0.0', 'txn2', omit=('runtimes/', 'models/'))
        self.assertTrue(second.activation_pending)
        self.assertEqual(weight.stat().st_mtime_ns, modified)
        receipt = installer.activate_release(self.plugin, '2.0.0')
        self.assertEqual(receipt.previous_version, '1.0.0')
        installer.activate_release(self.plugin, '1.0.0')
        self.assertEqual(installer.read_install_status(self.plugin).state, 'ready')
        self.assertTrue((self.plugin / 'versions' / '2.0.0').exists())

    def test_corrupt_reused_model_or_activation_payload_cannot_be_ready(self):
        self.install()
        weight = self.plugin / 'models' / 'fixture' / '1' / 'model.onnx'
        weight.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            self.install('2.0.0', 'badreuse', omit=('runtimes/', 'models/'))
        with self.assertRaises(ValueError):
            installer.activate_release(self.plugin, '1.0.0')
        self.assertNotEqual(installer.read_install_status(self.plugin).state, 'ready')

    def test_missing_distributed_weights_is_rejected_candidates_do_not_require_them(self):
        def missing(manifest, files):
            manifest['models'] = []
            manifest['files'] = [f for f in manifest['files'] if not f['path'].startswith('models/')]
            for key in list(files):
                if key.startswith('models/'):
                    del files[key]
        with self.assertRaises(ValueError):
            self.install(mutate=missing)
        def candidate(manifest, files):
            missing(manifest, files)
            catalog = json.loads(files['code/catalog/models.json'])
            catalog['models'][0]['catalog_state'] = 'candidate'
            files['code/catalog/models.json'] = json.dumps(catalog).encode()
            for record in manifest['files']:
                if record['path'] == 'code/catalog/models.json':
                    record.update(size=len(files[record['path']]), sha256=digest(files[record['path']]))
        self.assertTrue(self.install(transaction='candidate', mutate=candidate).activation_pending)

    def test_publish_failure_rolls_back_new_code_and_preserves_active_pointer(self):
        self.install()
        installer.activate_release(self.plugin, '1.0.0')
        before = (self.plugin / 'installation.json').read_bytes()
        original = installer._atomic_json
        def failing(path, values):
            if Path(path).name == 'installation.json' and values.get('pending_version') == '2.0.0':
                raise OSError('synthetic disk failure')
            return original(path, values)
        with patch.object(installer, '_atomic_json', side_effect=failing):
            with self.assertRaises(OSError):
                self.install('2.0.0', 'failcommit')
        self.assertEqual((self.plugin / 'installation.json').read_bytes(), before)
        self.assertFalse((self.plugin / 'versions' / '2.0.0').exists())

    def test_recovers_after_process_death_between_atomic_component_promotions(self):
        # Crash remnants are verified in isolation until missing components are promoted.
        package = fixture_package(self.root)
        with zipfile.ZipFile(package['path']) as zipped:
            code = self.plugin / 'versions' / '1.0.0'
            code.mkdir(parents=True)
            for entry in zipped.infolist():
                if entry.filename.startswith('code/'):
                    target = code / entry.filename[5:]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zipped.read(entry))
            (code / 'release-manifest.json').write_bytes(zipped.read('release-manifest.json'))
        receipt = installer.begin_install(self.host, package, 'resumecrash')
        self.assertTrue(receipt.activation_pending)
        installer.activate_release(self.plugin, '1.0.0')
        self.assertEqual(installer.read_install_status(self.plugin).state, 'ready')

    def test_atomic_status_retries_transient_windows_file_sharing_failure(self):
        destination = self.root / 'state.json'
        real_replace = os.replace
        attempts = []
        def transient(source, target):
            attempts.append(True)
            if len(attempts) == 1:
                error = PermissionError('synthetic Windows file sharing')
                error.winerror = 5
                raise error
            return real_replace(source, target)
        with patch.object(installer.os, 'replace', side_effect=transient):
            installer._atomic_json(destination, {'state': 'ready'})
        self.assertEqual(json.loads(destination.read_text()), {'state': 'ready'})

    def test_powershell_entrypoint_installs_from_other_working_directory(self):
        powershell = shutil.which('powershell') or shutil.which('pwsh')
        if not powershell:
            self.skipTest('PowerShell não disponível.')
        package = fixture_package(self.root)
        script = Path(__file__).resolve().parents[1] / 'installer' / 'INSTALL.ps1'
        result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                 '-File', str(script), '-SuiteRoot', str(self.host),
                                 '-PackagePath', package['path'], '-PackageSha256', package['sha256'],
                                 '-TransactionId', 'powershell', '-BootstrapPython', sys.executable],
                                cwd=self.root, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(installer.read_install_status(self.plugin).state, 'installed_pending_restart')

    def test_zip_bomb_and_case_collisions_are_rejected(self):
        for index, name in enumerate(('code/MODULE.JSON', 'code/bomb.bin')):
            package = fixture_package(self.root)
            with zipfile.ZipFile(package['path'], 'a', compression=zipfile.ZIP_DEFLATED) as zipped:
                zipped.writestr(name, b'0' * (2_000_000 if index else 1))
            package['sha256'] = digest(Path(package['path']).read_bytes())
            with self.assertRaises(ValueError):
                installer.begin_install(self.host, package, 'zipbad' + str(index))

    def test_status_without_installation_cannot_claim_ready(self):
        self.plugin.mkdir(parents=True)
        (self.plugin / 'install-status.json').write_text(json.dumps({
            'state': 'ready', 'transaction_id': 'forged', 'stage': 'active'}))
        self.assertNotEqual(installer.read_install_status(self.plugin).state, 'ready')

    def test_catalog_hash_mismatch_and_incomplete_runtime_are_rejected(self):
        def mismatch(manifest, files):
            record = next(r for r in manifest['files'] if r['path'].endswith('model.onnx'))
            files[record['path']] = b'different synthetic weight'
            record.update(size=len(files[record['path']]), sha256=digest(files[record['path']]))
        with self.assertRaises(ValueError):
            self.install(mutate=mismatch)
        with self.assertRaises(ValueError):
            self.install(transaction='noruntime', omit=('runtimes/',))

    def test_partial_extraction_failure_removes_only_transaction_payload(self):
        self.install()
        installer.activate_release(self.plugin, '1.0.0')
        before = (self.plugin / 'installation.json').read_bytes()
        original = installer._copy_stream
        package = fixture_package(self.root, '2.0.0')
        calls = []
        def interrupted(source, destination, progress=None):
            calls.append(True)
            if len(calls) == 3:
                destination.write(source.read(2))
                raise KeyboardInterrupt()
            return original(source, destination, progress)
        with patch.object(installer, '_copy_stream', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                installer.begin_install(self.host, package, 'copycancel')
        self.assertEqual((self.plugin / 'installation.json').read_bytes(), before)
        self.assertFalse((self.plugin / 'versions' / '2.0.0').exists())
        self.assertTrue(installer.begin_install(self.host, package, 'copycancel').activation_pending)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows junction boundary')
    def test_valid_package_ignores_unrelated_cwd_code_junction(self):
        unrelated = self.root / 'unrelated cwd'
        unrelated.mkdir()
        outside = self.root / 'unrelated target'
        outside.mkdir()
        junction = unrelated / 'code'
        made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(outside)], capture_output=True)
        self.assertEqual(made.returncode, 0)
        package = fixture_package(self.root)
        previous_cwd = Path.cwd()
        try:
            os.chdir(unrelated)
            self.assertTrue(installer.begin_install(self.host, package, 'cwdjunction').activation_pending)
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            os.chdir(previous_cwd)
            junction.rmdir()

    @unittest.skipUnless(sys.platform == 'win32', 'Windows junction boundary')
    def test_junctioned_storage_is_rejected(self):
        self.plugin.mkdir(parents=True)
        outside = self.root / 'outside'
        outside.mkdir()
        junction = self.plugin / 'models'
        made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(outside)], capture_output=True)
        self.assertEqual(made.returncode, 0)
        try:
            with self.assertRaises(ValueError):
                self.install()
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            junction.rmdir()


if __name__ == '__main__':
    unittest.main()

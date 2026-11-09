"""Small synthetic packages exercise durable progress without scientific code."""
from dataclasses import asdict
import errno
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from neuro_rt import install_state as installer
from test_plugin_install import fixture_package, digest


class InstallProgressTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='progress ', dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.host = self.root / 'Suite synthetique'
        self.host.mkdir()
        for name in ('radai_panel.py', 'radai_ui.py', 'entrega.txt'):
            (self.host / name).write_text('synthetic host marker', encoding='utf-8')
        self.plugin = self.host / 'Plugins/NEURO RT'

    def capture_status(self, package):
        statuses = []
        original = installer._atomic_json
        def record(path, value):
            if Path(path).name == 'install-status.json':
                statuses.append(dict(value))
            return original(path, value)
        with patch.object(installer, '_atomic_json', side_effect=record):
            receipt = installer.begin_install(self.host, package, 'progress1')
        return receipt, statuses

    def test_fresh_install_publishes_phases_and_monotonic_inventory_counters(self):
        _, statuses = self.capture_status(fixture_package(self.root))
        phases = [value['stage'] for value in statuses]
        for phase in ('checking', 'copying', 'verifying', 'extracting', 'validating', 'publishing', 'complete'):
            self.assertIn(phase, phases)
        for key in ('completed_files', 'processed_bytes'):
            values = [value[key] for value in statuses]
            self.assertEqual(values, sorted(values), key)
        final = statuses[-1]
        self.assertEqual(final['completed_files'], final['total_files'])
        self.assertEqual(final['processed_bytes'], final['total_unpacked_bytes'])
        self.assertGreater(final['completed_files'], 0)
        self.assertEqual(asdict(installer.read_install_status(self.plugin)), final)

    def test_progress_is_throttled_for_many_files_but_final_counts_are_durable(self):
        def many(manifest, files):
            for index in range(160):
                name = 'code/web/synthetic-%03d.js' % index
                content = ('synthetic-%03d' % index).encode()
                files[name] = content
                manifest['files'].append({'path': name, 'size': len(content), 'sha256': digest(content)})
        package = fixture_package(self.root, mutate=many)
        with patch.object(installer.time, 'monotonic', return_value=10.0):
            _, statuses = self.capture_status(package)
        self.assertEqual(statuses[-1]['completed_files'], 168)
        self.assertLess(len(statuses), 20, 'Do not fsync a JSON status for every payload file.')

    def test_hash_failure_records_safe_stage_and_code_without_altering_active_pointer(self):
        package = fixture_package(self.root)
        package['sha256'] = '0'*64
        with self.assertRaises(ValueError):
            installer.begin_install(self.host, package, 'badsha')
        value = json.loads((self.plugin / 'install-status.json').read_text(encoding='utf-8'))
        self.assertEqual(value['state'], 'failed')
        self.assertEqual(value['error_code'], 'PACKAGE_INTEGRITY')
        self.assertEqual(value['error_stage'], 'verifying')
        self.assertFalse((self.plugin / 'installation.json').exists())

    def test_reused_components_are_counted_once_with_the_new_code_inventory(self):
        installer.begin_install(self.host, fixture_package(self.root), 'existing')
        _, statuses = self.capture_status(fixture_package(self.root, version='2.0.0'))
        final = statuses[-1]
        self.assertEqual(final['completed_files'], 8)
        self.assertEqual(final['completed_files'], final['total_files'])
        self.assertEqual(final['processed_bytes'], final['total_unpacked_bytes'])
        self.assertEqual([v['processed_bytes'] for v in statuses],
                         sorted(v['processed_bytes'] for v in statuses))

    def test_safe_diagnostics_never_include_exception_arguments_or_paths(self):
        sensitive = 'PATIENT-SECRET C:/patients/private-file.dcm'
        error = PermissionError(errno.EACCES, sensitive, sensitive)
        result = installer.sanitize_install_error(error, 'extracting')
        self.assertEqual(result['error_code'], 'PERMISSION_DENIED')
        self.assertEqual(result['error_stage'], 'extracting')
        self.assertEqual(result['os_errno'], errno.EACCES)
        self.assertNotIn('PATIENT', json.dumps(result))
        self.assertNotIn('patients', json.dumps(result))
        unknown = installer.sanitize_install_error(RuntimeError(sensitive), sensitive)
        self.assertEqual(unknown['error_stage'], 'unknown')
        self.assertNotIn('PATIENT', json.dumps(unknown))

    def test_safe_diagnostics_distinguish_disk_full_busy_and_cancelled(self):
        disk = installer.sanitize_install_error(OSError(errno.ENOSPC, 'secret'), 'copying')
        self.assertEqual(disk['error_code'], 'INSUFFICIENT_SPACE')
        busy = PermissionError(errno.EACCES, 'secret')
        busy.winerror = 32
        self.assertEqual(installer.sanitize_install_error(busy, 'publishing')['error_code'], 'FILE_BUSY')
        self.assertEqual(installer.sanitize_install_error(KeyboardInterrupt(), 'extracting')['error_code'], 'CANCELLED')


if __name__ == '__main__':
    unittest.main()

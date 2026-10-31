"""Post-commit cleanup is maintenance, never a rollback of verified installation."""
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from neuro_rt import install_state as installer
from test_plugin_install import fixture_package


class InstallCleanupTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='cleanup ', dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.host = self.root / 'Suite synthetique'
        self.host.mkdir()
        for name in ('radai_panel.py', 'radai_ui.py', 'entrega.txt'):
            (self.host / name).write_text('synthetic marker', encoding='utf-8')
        self.plugin = self.host / 'Plugins/NEURO RT'

    @staticmethod
    def denied():
        value = PermissionError(13, 'synthetic cleanup denial')
        value.winerror = 5
        return value

    def test_postcommit_denial_preserves_pending_install_and_retries_same_transaction(self):
        package = fixture_package(self.root)
        with patch.object(installer, '_safe_remove_tree', side_effect=self.denied()):
            receipt = installer.begin_install(self.host, package, 'postcommit')
        self.assertEqual(receipt.version, '1.0.0')
        status = installer.read_install_status(self.plugin)
        self.assertEqual(status.state, 'installed_pending_restart')
        self.assertTrue(status.cleanup_pending)
        self.assertEqual(status.cleanup_error_code, 'PERMISSION_DENIED')
        state = json.loads((self.plugin / 'installation.json').read_text(encoding='utf-8'))
        self.assertEqual(state['pending_version'], '1.0.0')
        self.assertIsNone(state['active_version'])
        marker = self.plugin / 'transactions/postcommit/cleanup.json'
        self.assertTrue(json.loads(marker.read_text(encoding='utf-8'))['pending'])
        self.assertEqual(installer.begin_install(self.host, package, 'postcommit'), receipt)
        self.assertFalse((self.plugin / 'staging/postcommit').exists())
        self.assertFalse(installer.read_install_status(self.plugin).cleanup_pending)
        self.assertFalse(json.loads(marker.read_text(encoding='utf-8'))['pending'])

    def test_next_prepare_retries_only_owned_staging(self):
        with patch.object(installer, '_safe_remove_tree', side_effect=self.denied()):
            installer.begin_install(self.host, fixture_package(self.root), 'previous')
        downloads = self.plugin / 'staging/downloads'
        downloads.mkdir()
        (downloads / 'keep.zip').write_bytes(b'not part of transaction cleanup')
        (self.plugin / 'data/keep.txt').write_bytes(b'private data placeholder')
        installer.begin_install(self.host, fixture_package(self.root, '2.0.0'), 'next')
        self.assertFalse((self.plugin / 'staging/previous').exists())
        self.assertTrue((downloads / 'keep.zip').is_file())
        self.assertEqual((self.plugin / 'data/keep.txt').read_bytes(), b'private data placeholder')
        self.assertFalse(installer.read_install_status(self.plugin).cleanup_pending)

    def test_precommit_cleanup_failure_does_not_mask_primary_error_or_active_pointer(self):
        installer.begin_install(self.host, fixture_package(self.root), 'active')
        installer.activate_release(self.plugin, '1.0.0')
        previous = (self.plugin / 'installation.json').read_bytes()
        primary = ValueError('primary synthetic publication failure')
        original = installer._atomic_json
        def publish(path, values):
            if Path(path) == self.plugin / 'installation.json' and values.get('pending_version') == '2.0.0':
                raise primary
            return original(path, values)
        with patch.object(installer, '_atomic_json', side_effect=publish), \
             patch.object(installer, '_safe_remove_tree', side_effect=self.denied()):
            with self.assertRaises(ValueError) as caught:
                installer.begin_install(self.host, fixture_package(self.root, '2.0.0'), 'precommit')
        self.assertIs(caught.exception, primary)
        self.assertEqual((self.plugin / 'installation.json').read_bytes(), previous)
        value = installer.read_install_status(self.plugin)
        self.assertEqual(value.state, 'failed')
        self.assertTrue(value.rollback_cleanup_pending)

    @unittest.skipUnless(os.name == 'nt', 'Windows ReadOnly directory attribute.')
    def test_owned_readonly_directory_is_retried_without_changing_external_paths(self):
        target = self.root / 'owned/temporary'
        nested = target / 'readonly-child'
        nested.mkdir(parents=True)
        nested.chmod(stat.S_IREAD)
        self.assertTrue(nested.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)
        installer._safe_remove_tree(target, self.root / 'owned')
        self.assertFalse(target.exists())

    def test_restart_and_host_validation_stages_remain_diagnostic_tokens(self):
        for stage in ('restart', 'host_validation'):
            self.assertEqual(installer.sanitize_install_error(ValueError('synthetic'), stage)['error_stage'], stage)

    def test_postcommit_receipt_write_denial_is_maintenance_not_install_failure(self):
        original = installer._atomic_json
        def write(path, values):
            if Path(path).name == 'receipt.json':
                raise self.denied()
            return original(path, values)
        with patch.object(installer, '_atomic_json', side_effect=write):
            result = installer.begin_install(self.host, fixture_package(self.root), 'metadata')
        self.assertTrue(result.activation_pending)
        value = installer.read_install_status(self.plugin)
        self.assertEqual(value.state, 'installed_pending_restart')
        self.assertTrue(value.cleanup_pending)
        self.assertEqual(value.error_code, '')

    def test_cleanup_journal_cannot_redirect_deletion_outside_owned_staging(self):
        outside = self.root / 'outside'
        outside.mkdir()
        keep = outside / 'keep.txt'
        keep.write_bytes(b'keep')
        bad = self.plugin / 'transactions/bad'
        bad.mkdir(parents=True)
        (bad / 'identity.json').write_text(json.dumps({'sha256': '0'*64}), encoding='utf-8')
        (bad / 'cleanup.json').write_text(json.dumps({'schema': 'neuro-rt/staging-cleanup/1',
            'transaction_id': '../outside', 'pending': True}), encoding='utf-8')
        installer.begin_install(self.host, fixture_package(self.root), 'normal')
        self.assertEqual(keep.read_bytes(), b'keep')
        self.assertTrue(installer.read_install_status(self.plugin).cleanup_pending)


if __name__ == '__main__':
    unittest.main()

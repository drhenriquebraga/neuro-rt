"""Synthetic trusted bootstrap/CLI checks; no downloads or scientific workers."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from neuro_rt import install_state, plugin_consent, plugin_update
from scripts.build_host_bootstrap import generate

ROOT = Path(__file__).resolve().parents[1]


class InstallerConsentTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / 'runtime/test-tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_generated_provider_shares_policy_and_guards_every_install_action_before_queue(self):
        path = generate(self.root / 'bootstrap.py')
        spec = importlib.util.spec_from_file_location('synthetic_consent_bootstrap', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue('plugin_consent' in module.SOURCES, 'Policy must be pinned in trusted bootstrap')
        with patch.dict(sys.modules):
            for key in list(sys.modules):
                if key.startswith('_radai_neuro_bootstrap'):
                    sys.modules.pop(key)
            update = module._load_private_installer()
            events = []
            class Coordinator:
                def __init__(self, *args, **kwargs): pass
                def request_plugin_update(self, plugin_id, action):
                    events.append(action)
                    return {'state': 'preparing'}
            with patch.object(update, 'UpdateCoordinator', Coordinator):
                provider = module.build_provider(self.root, {'version': '8.10'}, {})
                self.assertEqual(provider.consent_policy(), plugin_consent.policy())
                self.assertFalse(provider.consent_status()['installation_accepted'])
                for action in ('comecar', 'esperar', 'interromper'):
                    with self.subTest(action=action), self.assertRaises(ValueError):
                        provider.request_plugin_update('neuro-rt', action)
                with self.assertRaises(ValueError): provider.install()
                self.assertEqual(events, [])
                current = provider.consent_policy()
                provider.accept_consent(dict(accepted=True, version=current['version'], digest=current['digest']))
                self.assertTrue(provider.consent_status()['installation_accepted'])
                self.assertFalse(provider.consent_status()['first_use_accepted'])
                self.assertEqual(provider.install()['state'], 'preparing')
                self.assertEqual(events, ['comecar'])

    def test_direct_installer_cli_refuses_without_consent_before_prepare(self):
        args = ['--suite-root', str(self.root), '--package-path', 'synthetic.zip',
                '--package-sha256', 'a'*64, '--transaction-id', 'test']
        with patch.object(install_state, 'begin_install') as prepare, contextlib.redirect_stdout(io.StringIO()):
            self.assertNotEqual(install_state.main(args), 0)
            prepare.assert_not_called()

    def test_latest_cli_refuses_without_consent_before_network_or_coordinator(self):
        with patch.object(plugin_update, 'UpdateCoordinator') as coordinator, contextlib.redirect_stdout(io.StringIO()):
            self.assertNotEqual(plugin_update.main(['--suite-root', str(self.root), '--host-version', '8.10']), 0)
            coordinator.assert_not_called()

    def test_powershell_without_acknowledgement_stops_before_installation(self):
        powershell = shutil.which('powershell') or shutil.which('pwsh')
        if not powershell:
            self.skipTest('PowerShell não disponível.')
        host = self.root / 'Host'
        host.mkdir()
        package = self.root / 'package.zip'
        package.write_bytes(b'not reached')
        run = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                              '-File', str(ROOT / 'installer/INSTALL.ps1'), '-SuiteRoot', str(host),
                              '-PackagePath', str(package), '-PackageSha256', 'a'*64,
                              '-TransactionId', 'without-consent', '-BootstrapPython', sys.executable,
                              '-HostVersion', '8.11', '-LegacyPrepareForQA'],
                             input='', capture_output=True, text=True, timeout=30)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('ACEITO', run.stdout)
        self.assertFalse((host / 'Plugins/NEURO RT/installation.json').exists())
        self.assertFalse(plugin_consent.accepted(plugin_consent.config_for_suite(host), 'installation'))


if __name__ == '__main__': unittest.main()

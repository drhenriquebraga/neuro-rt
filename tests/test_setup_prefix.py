"""Light SETUP payload prefixes do not change logical authenticated paths."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from host_setup_fixtures import host_setup
from neuro_rt import install_state
from neuro_rt.plugin_update import UpdateCoordinator


class PrefixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='neuro-setup-prefix-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = host_setup(self.root)
        self.wrapped = self.root / 'wrapped.zip'
        with zipfile.ZipFile(self.base['path']) as incoming, zipfile.ZipFile(self.wrapped, 'w') as output:
            output.writestr('README.txt', 'Synthetic setup only')
            output.writestr('START_HERE_TO_INSTALL_NEURO_RT.cmd', '@echo off\n')
            for name in incoming.namelist():
                output.writestr('programa/' + name, incoming.read(name))

    def test_wrapped_and_flat_packages_have_identical_logical_inventory(self):
        inventories = []
        for file in (self.base['path'], self.wrapped):
            with zipfile.ZipFile(file) as raw:
                archive = install_state.setup_archive(raw)
                inventories.append(install_state._inspect_zip(archive)[0])
                self.assertEqual(json.loads(archive.read('code/module.json'))['id'], 'neuro-rt')
        self.assertEqual(inventories[0], inventories[1])

    def test_real_coordinator_can_prepare_wrapped_online_code_without_executing_root_starter(self):
        host = self.root / 'host'
        host.mkdir()
        for name, value in [('radai_panel.py', '# synthetic'), ('radai_ui.py', '# synthetic'), ('entrega.txt', 'VERSAO=8.20\n')]:
            (host / name).write_text(value)
        package = {'path': str(self.wrapped), 'sha256': hashlib.sha256(self.wrapped.read_bytes()).hexdigest()}
        coordinator = UpdateCoordinator(host, host_version='8.20', host_python=sys.executable,
            hold=lambda _: None, busy=lambda: False, cancel=lambda: None, restart=None)
        with patch('importlib.metadata.version', return_value='1.0'):
            coordinator.prepare(package, require_host=True)
        state = json.loads((host / 'Plugins/NEURO RT/installation.json').read_text())
        self.assertEqual(state['pending_version'], '1.0.2')

    def test_unexpected_outside_payload_files_are_rejected(self):
        with zipfile.ZipFile(self.wrapped, 'a') as archive:
            archive.writestr('untrusted.exe', b'do not run')
        with zipfile.ZipFile(self.wrapped) as raw, self.assertRaises(ValueError):
            install_state._inspect_zip(install_state.setup_archive(raw))


if __name__ == '__main__':
    unittest.main()

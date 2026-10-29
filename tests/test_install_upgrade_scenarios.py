"""Real host PowerShell updater against disposable synthetic stations only."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

HOST = Path(__file__).resolve().parents[2] / 'AUTO_CONTORNO'


@unittest.skipUnless(os.name == 'nt', 'Host updater is Windows PowerShell.')
class HostUpgradeScenarios(unittest.TestCase):
    def test_base_reinstall_preserves_plugin_caches_and_data(self):
        sys.path.insert(0, str(HOST / 'tools'))
        import test_installer as host_fixture
        base = Path(__file__).resolve().parents[1] / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            tmp = Path(tmp)
            origin, output, extracted, destination = (tmp / n for n in ('origin', 'output', 'extracted', 'destination'))
            host_fixture.montar_fantoma(str(origin))
            package = host_fixture.empacotar(str(origin), str(output), versao='8.10')
            host_fixture._extrair(package, str(extracted))
            installed = destination / 'AUTO_CONTORNO'
            keep = installed / 'Plugins/NEURO RT/versions/1.0.0/__pycache__/keep.pyc'
            keep.parent.mkdir(parents=True)
            keep.write_bytes(b'synthetic plugin cache sentinel')
            rc, result = host_fixture.instalar(str(extracted), str(destination))
            self.assertEqual(rc, 0, result[-1800:])
            self.assertEqual(keep.read_bytes(), b'synthetic plugin cache sentinel')

    def test_host_code_update_preserves_plugin_tree_and_backs_up_only_legacy_base_modules(self):
        sys.path.insert(0, str(HOST / 'tools'))
        import test_installer as host_fixture
        base = Path(__file__).resolve().parents[1] / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            package = host_fixture.montar_pacote_leve(tmp, '8.10')
            _, installed = host_fixture.montar_instalacao_leve(tmp, '8.9', package, host_fixture._porta_livre())
            installed = Path(installed)
            paths = ('Plugins/NEURO RT/data/result.json', 'Plugins/NEURO RT/config/settings.json',
                     'Plugins/NEURO RT/models/model/1/weight.bin',
                     'Plugins/NEURO RT/versions/1.0.0/module.json', 'calibracao/keep.txt')
            before = {}
            for name in paths:
                path = installed / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(('synthetic preserve ' + name).encode())
                before[name] = path.read_bytes()
            legacy = b'# synthetic old base module\n'
            for name in ('radai_nidus.py', 'radai_nidus_screen.py'):
                (installed / name).write_bytes(legacy)
            rc, output = host_fixture._rodar_atualizar(package, ['-Destino', str(installed),
                '-Python', sys.executable, '-SemPerguntar'], {'LOCALAPPDATA': str(Path(tmp) / 'local'),
                    'RADAI_ATALHOS_NA_RAIZ': '1'})
            self.assertEqual(rc, 0, output[-1800:])
            for name, value in before.items():
                self.assertEqual((installed / name).read_bytes(), value)
            digest = hashlib.sha256(legacy).hexdigest()
            for name in ('radai_nidus.py', 'radai_nidus_screen.py'):
                self.assertFalse((installed / name).exists())
                backup = installed / '.migration-backups/neuro-rt-v1' / (digest + '-' + name)
                self.assertEqual(backup.read_bytes(), legacy)

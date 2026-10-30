import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_pipeline import TEMP_ROOT


class HostImportTests(unittest.TestCase):
    def test_export_capability_recognizes_modular_host_without_importing_engine(self):
        from neuro_rt.service import Settings
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            host = root / 'suite'
            (host / 'app').mkdir(parents=True)
            (host / 'tools').mkdir()
            engine = root / 'component-app/engine.py'
            engine.parent.mkdir()
            engine.write_text('raise RuntimeError("must not import scientific engine during status")')
            (host / 'tools/_componentes.py').write_text(
                'from pathlib import Path\n'
                'def arquivos(sub, padrao="*.py", suite=None):\n'
                '    return [str(Path(suite).parent/"component-app"/padrao)]\n')
            python = host / 'python.exe'
            python.write_bytes(b'fixture')
            settings = Settings(root)
            settings.host_app = host / 'app'
            settings.host_python = str(python)
            self.assertTrue(settings.export_available)

    def test_source_host_uses_its_component_resolver(self):
        from integration.host_imports import prepare_host_imports
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            (root / 'app').mkdir()
            (root / 'tools').mkdir()
            component = root / 'component-app'
            component.mkdir()
            (root / 'tools/_componentes.py').write_text(
                'import sys\nfrom pathlib import Path\n'
                'def ligar_caminho(suite=None):\n'
                '    sys.path.insert(0, str(Path(suite)/"component-app"))\n')
            with patch.object(sys, 'path', list(sys.path)):
                prepare_host_imports(root / 'app')
                self.assertIn(str(component), sys.path)
                self.assertIn(str(root / 'app'), sys.path)

    def test_flat_bundle_and_invalid_host(self):
        from integration.host_imports import prepare_host_imports
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            with patch.object(sys, 'path', list(sys.path)):
                prepare_host_imports(root)
                self.assertIn(str(root), sys.path)
            with self.assertRaises(ValueError):
                prepare_host_imports(root / 'missing')

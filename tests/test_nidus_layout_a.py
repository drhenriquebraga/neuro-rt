"""Exercise the real Nidus screen using synthetic browser responses only."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LayoutA(unittest.TestCase):
    def test_native_screen_layout_interactions_and_full_quality_restore(self):
        host = Path(os.environ.get('NEURO_HOST_ROOT', ''))
        playwright = Path(os.environ.get('NEURO_PLAYWRIGHT_MODULE', ''))
        if not (host/'app/radai_menu.py').is_file() or not playwright.is_dir() or not shutil.which('node'):
            self.skipTest('Set NEURO_HOST_ROOT and NEURO_PLAYWRIGHT_MODULE for the host browser check.')
        component = host/'_montagem/componentes/RECON_3D/app'
        if not component.is_dir():
            component = host.parent/'RECON_3D/app'
        with tempfile.TemporaryDirectory(prefix='nidus-a-synthetic-') as folder:
            html = Path(folder)/'screen.html'
            generator = (
                'import sys,pathlib;root=pathlib.Path(sys.argv[1]);host=pathlib.Path(sys.argv[2]);'
                'component=pathlib.Path(sys.argv[3]);'
                'sys.path[:0]=[str(root),str(root/"app"),str(host/"app"),str(component)];'
                'import radai_nidus_screen as s,radai_menu;'
                'from integration.localization import with_catalog;'
                'pathlib.Path(sys.argv[4]).write_text(with_catalog(radai_menu.aplicar(s.pagina(),"nidus_projecao"),"neuro"),encoding="utf8")')
            created = subprocess.run([sys.executable,'-I','-B','-c',generator,str(ROOT),str(host),str(component),str(html)],
                capture_output=True,text=True,encoding='utf8',errors='replace',timeout=30)
            self.assertEqual(created.returncode,0,created.stdout+created.stderr)
            checked = subprocess.run([shutil.which('node'),str(ROOT/'tests/nidus_layout_a_browser.cjs'),str(html)],
                capture_output=True,text=True,encoding='utf8',errors='replace',timeout=60)
            self.assertEqual(checked.returncode,0,checked.stdout+checked.stderr)
            self.assertIn('PASS: A grid',checked.stdout)


if __name__ == '__main__':
    unittest.main()

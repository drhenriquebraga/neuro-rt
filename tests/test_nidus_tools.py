"""Integrate NIDUS adapters with the shared host toolbar using synthetic data."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NidusTools(unittest.TestCase):
    def test_brush_mesh_and_folder_workflow(self):
        host = Path(os.environ.get('NEURO_HOST_ROOT', ''))
        playwright = Path(os.environ.get('NEURO_PLAYWRIGHT_MODULE', ''))
        if not (host/'app/radai_menu.py').is_file() or not playwright.is_dir() or not shutil.which('node'):
            self.skipTest('Set NEURO_HOST_ROOT and NEURO_PLAYWRIGHT_MODULE for host browser checks.')
        component = host/'_montagem/componentes/RECON_3D/app'
        with tempfile.TemporaryDirectory(prefix='nidus-tools-') as folder:
            html = Path(folder)/'screen.html'
            generator = (
                'import sys,pathlib;root=pathlib.Path(sys.argv[1]);host=pathlib.Path(sys.argv[2]);'
                'sys.path[:0]=[str(root),str(root/"app"),str(host/"app"),sys.argv[3]];'
                'import radai_nidus_screen as s,radai_menu;from integration.localization import with_catalog;'
                'pathlib.Path(sys.argv[4]).write_text(with_catalog(radai_menu.aplicar(s.pagina(),"nidus_projecao"),"neuro","nidus-temporal"),encoding="utf8")')
            generated = subprocess.run([sys.executable, '-I', '-B', '-c', generator, str(ROOT), str(host), str(component), str(html)],
                                       capture_output=True, text=True, encoding='utf8', errors='replace', timeout=30)
            self.assertEqual(generated.returncode, 0, generated.stdout+generated.stderr)
            args = [shutil.which('node'), str(ROOT/'tests/nidus_tools_browser.cjs'), str(html)]
            review = os.environ.get('NEURO_TOOLS_REVIEW')
            if review:
                Path(review).mkdir(parents=True, exist_ok=True)
                shutil.copyfile(html, Path(review)/'screen.html')
                args.append(review)
            tested = subprocess.run(args, capture_output=True, text=True, encoding='utf8', errors='replace', timeout=90)
            self.assertEqual(tested.returncode, 0, tested.stdout+tested.stderr)
            self.assertIn('PASS: shared NIDUS tools', tested.stdout)


if __name__ == '__main__':
    unittest.main()

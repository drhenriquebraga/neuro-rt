"""Image preparation checks use only synthetic pixels and mocked local routes."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NidusPreload(unittest.TestCase):
    def test_serial_cache_cancellation_and_memory_bounds(self):
        if not shutil.which('node'):
            self.skipTest('Node is required for the browser helper check.')
        run = subprocess.run([shutil.which('node'), str(ROOT/'tests/nidus_preload_unit.cjs')],
                             capture_output=True, text=True, encoding='utf8', timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout+run.stderr)

    def test_first_series_readiness_and_interactive_cache(self):
        host = Path(os.environ.get('NEURO_HOST_ROOT', ''))
        playwright = Path(os.environ.get('NEURO_PLAYWRIGHT_MODULE', ''))
        if not (host/'app/radai_menu.py').is_file() or not playwright.is_dir() or not shutil.which('node'):
            self.skipTest('Set NEURO_HOST_ROOT and NEURO_PLAYWRIGHT_MODULE for the host browser check.')
        component = host/'_montagem/componentes/RECON_3D/app'
        with tempfile.TemporaryDirectory(prefix='nidus-preload-synthetic-') as folder:
            html = Path(folder)/'screen.html'
            code = (
                'import sys,pathlib;root=pathlib.Path(sys.argv[1]);host=pathlib.Path(sys.argv[2]);'
                'component=pathlib.Path(sys.argv[3]);'
                'sys.path[:0]=[str(root),str(root/"app"),str(host/"app"),str(component)];'
                'import radai_nidus_screen as s,radai_menu;'
                'from integration.localization import with_catalog;'
                'pathlib.Path(sys.argv[4]).write_text(with_catalog(radai_menu.aplicar(s.pagina(),"nidus_projecao"),"neuro","nidus-temporal"),encoding="utf8")')
            generated = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(ROOT), str(host), str(component), str(html)],
                                       capture_output=True, text=True, encoding='utf8', errors='replace', timeout=30)
            self.assertEqual(generated.returncode, 0, generated.stdout+generated.stderr)
            args = [shutil.which('node'), str(ROOT/'tests/nidus_preload_browser.cjs'), str(html)]
            review = os.environ.get('NEURO_PRELOAD_REVIEW')
            if review:
                target = Path(review)
                target.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(html, target/'screen.html')
                args.append(str(target))
            checked = subprocess.run(args, capture_output=True, text=True, encoding='utf8', errors='replace', timeout=60)
            self.assertEqual(checked.returncode, 0, checked.stdout+checked.stderr)
            self.assertIn('PASS: blocking preparation', checked.stdout)


if __name__ == '__main__':
    unittest.main()

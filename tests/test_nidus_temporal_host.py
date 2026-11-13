"""Real host DOM smoke test; all series, pixels and temporal responses are synthetic."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TemporalHost(unittest.TestCase):
    def test_integrated_cine_and_twelve_languages(self):
        host = Path(os.environ.get('NEURO_HOST_ROOT', ''))
        playwright = Path(os.environ.get('NEURO_PLAYWRIGHT_MODULE', ''))
        if not (host/'app/radai_menu.py').is_file() or not playwright.is_dir() or not shutil.which('node'):
            self.skipTest('Set NEURO_HOST_ROOT and NEURO_PLAYWRIGHT_MODULE for the host browser check.')
        component = host/'_montagem/componentes/RECON_3D/app'
        with tempfile.TemporaryDirectory(prefix='nidus-cine-host-') as folder:
            html, expected = Path(folder)/'screen.html', Path(folder)/'expected.json'
            generator = (
                'import sys,pathlib,json;root=pathlib.Path(sys.argv[1]);host=pathlib.Path(sys.argv[2]);'
                'sys.path[:0]=[str(root),str(root/"app"),str(host/"app"),sys.argv[3]];'
                'import radai_nidus_screen as s,radai_menu;'
                'from integration.localization import with_catalog;from neuro_rt.nidus_temporal_i18n import merge_catalog;'
                'pathlib.Path(sys.argv[4]).write_text(with_catalog(radai_menu.aplicar(s.pagina(),"nidus_projecao"),"neuro","nidus-temporal"),encoding="utf8");'
                'pathlib.Path(sys.argv[5]).write_text(json.dumps(merge_catalog({}),ensure_ascii=False),encoding="utf8")')
            created = subprocess.run([sys.executable, '-I', '-B', '-c', generator, str(ROOT), str(host), str(component), str(html), str(expected)],
                                     capture_output=True, text=True, encoding='utf8', errors='replace', timeout=30)
            self.assertEqual(created.returncode, 0, created.stdout+created.stderr)
            args = [shutil.which('node'), str(ROOT/'tests/nidus_temporal_host_browser.cjs'), str(html), str(expected)]
            review = os.environ.get('NEURO_TEMPORAL_REVIEW')
            if review:
                target = Path(review)
                target.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(html, target/'screen.html')
                shutil.copyfile(expected, target/'expected.json')
                args.append(str(target))
            checked = subprocess.run(args, capture_output=True, text=True, encoding='utf8', errors='replace', timeout=180)
            self.assertEqual(checked.returncode, 0, checked.stdout+checked.stderr)
            self.assertIn('12 languages.', checked.stdout)


if __name__ == '__main__':
    unittest.main()

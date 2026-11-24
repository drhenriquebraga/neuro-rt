"""Exercise the actual host composition and the per-series processing controls."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / 'neuro_rt.local.json'
CONFIG = json.loads(CONFIG_FILE.read_text(encoding='utf-8')) if CONFIG_FILE.exists() else {}
HOST = os.environ.get('NEURO_HOST_APP', CONFIG.get('host_app', ''))
PYTHON = os.environ.get('NEURO_STUDY_HOST_PYTHON', CONFIG.get('host_python', sys.executable))
PLAYWRIGHT = os.environ.get('NEURO_PLAYWRIGHT_MODULE', 'playwright')
CHROME = os.environ.get('NEURO_BROWSER_EXECUTABLE', 'C:/Program Files/Google/Chrome/Application/chrome.exe')


class ProcessingFormTests(unittest.TestCase):
    def test_every_host_language_has_all_processing_phrases(self):
        previous = json.loads((ROOT / 'web/study-i18n.json').read_text(encoding='utf-8'))
        current = json.loads((ROOT / 'web/process-i18n.json').read_text(encoding='utf-8'))
        self.assertEqual(set(current), set(previous))
        for code, phrases in current.items():
            self.assertEqual(set(phrases), set(current['pt-BR']), code)
            self.assertTrue(all(text.strip() for text in phrases.values()), code)

    @unittest.skipUnless(HOST and Path(HOST).is_dir(), 'Host da suíte indisponível.')
    def test_composed_form(self):
        temp_root = ROOT / 'runtime/test-tmp'
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as work:
            page = Path(work) / 'process.html'
            build = ('import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); '
                     'from integration.host_imports import prepare_host_imports; prepare_host_imports(sys.argv[2]); '
                     'from integration.neuro_process_screen import pagina_processo; '
                     'Path(sys.argv[3]).write_text(pagina_processo(),encoding="utf-8")')
            compose = subprocess.run([PYTHON, '-c', build, str(ROOT), HOST, str(page)], capture_output=True, timeout=50)
            self.assertEqual(compose.returncode, 0, compose.stderr.decode(errors='replace'))
            html = page.read_text(encoding='utf-8')
            for marker in ('id="nr-add-CT_form"', 'id="nr-add-MR_form"', 'id="radai_rev_corpo"', 'id="nr-plans"'):
                self.assertIn(marker, html)
            self.assertNotIn('id="result-series"', html)
            if shutil.which('node') and Path(PLAYWRIGHT).is_dir() and Path(CHROME).is_file():
                env = dict(os.environ, NEURO_BROWSER_EXECUTABLE=CHROME, NEURO_PLAYWRIGHT_MODULE=PLAYWRIGHT)
                browser = subprocess.run(['node', str(ROOT/'tests/neuro_process_browser.cjs'), str(page)],
                                         capture_output=True, env=env, timeout=90)
                self.assertEqual(browser.returncode, 0, browser.stderr.decode(errors='replace')[-3000:])
                self.assertIn(b'PASS:', browser.stdout)


if __name__ == '__main__':
    unittest.main()

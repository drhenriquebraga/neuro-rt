import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from neuro_rt.plugin_consent import policy

ROOT = Path(__file__).resolve().parents[1]
PLAYWRIGHT = os.environ.get('NEURO_PLAYWRIGHT_MODULE', 'C:/Users/henri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')
CHROME = os.environ.get('NEURO_BROWSER_EXECUTABLE', 'C:/Program Files/Google/Chrome/Application/chrome.exe')


class ConsentUpdateBrowserTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node') and Path(PLAYWRIGHT).is_dir() and Path(CHROME).is_file(),
                         'Node, Playwright ou navegador indisponível.')
    def test_installer_consumes_the_versioned_host_consent_contract(self):
        base = ROOT / 'runtime/test-tmp'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            document = Path(tmp) / 'policy.json'
            document.write_text(json.dumps(policy()), encoding='utf-8')
            env = dict(os.environ, NEURO_CONSENT_POLICY=str(document),
                       NEURO_PLAYWRIGHT_MODULE=PLAYWRIGHT, NEURO_BROWSER_EXECUTABLE=CHROME)
            run = subprocess.run([shutil.which('node'), str(ROOT / 'tests/consent_update_ui_browser.cjs')],
                                 env=env, capture_output=True, text=True, timeout=80)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('PASS:', run.stdout)
            print(run.stdout.strip())

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


class SettingsUpdateBrowserTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node') and Path(PLAYWRIGHT).is_dir() and Path(CHROME).is_file(),
                         'Node, Playwright ou navegador indisponível.')
    def test_local_source_refresh_and_external_lifecycle_settings(self):
        base = ROOT / 'runtime/test-tmp'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            document = Path(tmp) / 'policy.json'
            document.write_text(json.dumps(policy()), encoding='utf-8')
            env = dict(os.environ, NEURO_CONSENT_POLICY=str(document),
                       NEURO_PLAYWRIGHT_MODULE=PLAYWRIGHT, NEURO_BROWSER_EXECUTABLE=CHROME)
            result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/settings_update_ui_browser.cjs')],
                                    env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS:', result.stdout)
            print(result.stdout.strip())


if __name__ == '__main__': unittest.main()

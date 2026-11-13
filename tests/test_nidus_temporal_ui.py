"""Run optional Chrome/Playwright regression without app or patient dependencies."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _playwright_module(node):
    override = os.environ.get('PLAYWRIGHT_MODULE')
    if override:
        return override
    for candidate in (
        ROOT / 'node_modules' / 'playwright',
        Path.home() / '.cache' / 'codex-runtimes' / 'codex-primary-runtime' /
        'dependencies' / 'node' / 'node_modules' / 'playwright',
    ):
        if (candidate / 'package.json').is_file():
            return str(candidate)
    found = subprocess.run(
        [node, '-e', 'process.stdout.write(require.resolve("playwright"))'],
        cwd=str(ROOT), capture_output=True, text=True, timeout=15,
    )
    return found.stdout.strip() if found.returncode == 0 else None


class TemporalBrowser(unittest.TestCase):
    def test_temporal_ui_browser_regressions(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js is needed for the optional browser regression')
        module = _playwright_module(node)
        if not module:
            self.skipTest('Playwright is needed; set PLAYWRIGHT_MODULE or install it for tests')

        env = os.environ.copy()
        env['PLAYWRIGHT_MODULE'] = module
        env['NIDUS_PROJECT_ROOT'] = str(ROOT)
        if not env.get('CHROME_EXECUTABLE'):
            candidates = [
                Path(env.get('ProgramFiles', 'C:/Program Files')) /
                'Google' / 'Chrome' / 'Application' / 'chrome.exe',
                Path('/usr/bin/google-chrome'),
                Path('/usr/bin/chromium'),
                Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
            ]
            for candidate in candidates:
                if candidate.is_file():
                    env['CHROME_EXECUTABLE'] = str(candidate)
                    break
        # Without an installed Chrome override, Playwright uses its own Chromium.
        completed = subprocess.run(
            [node, str(ROOT / 'tests' / 'nidus_temporal_ui_browser.cjs'), str(ROOT)],
            cwd=str(ROOT), env=env, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=120,
        )
        self.assertEqual(
            completed.returncode, 0,
            'Temporal browser regression failed:\n' + completed.stdout + completed.stderr,
        )
        self.assertIn('9/9 passed', completed.stdout)


if __name__ == '__main__':
    unittest.main()

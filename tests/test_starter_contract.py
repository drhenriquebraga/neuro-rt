"""The public starter invokes a script file instead of evaluating its own text."""
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StarterContract(unittest.TestCase):
    def test_cmd_has_no_embedded_script_evaluation(self):
        starter = (ROOT / 'installer/START_HERE.cmd').read_text(encoding='utf-8-sig')
        for expression in (r'\[scriptblock\]\s*::\s*Create', r'\bInvoke-Expression\b',
                           r'-EncodedCommand\b', r'RADAI_BOOTSTRAP_SELF',
                           r'RADAI_BOOTSTRAP_POWERSHELL'):
            with self.subTest(expression=expression):
                self.assertIsNone(re.search(expression, starter, re.IGNORECASE))

    def test_corrective_release_requires_the_corrected_host(self):
        module = json.loads((ROOT / 'module.json').read_text(encoding='utf8'))
        self.assertEqual(module['version'], '1.3.8')
        self.assertEqual(module['host_min_version'], '8.24')


if __name__ == '__main__':
    unittest.main()

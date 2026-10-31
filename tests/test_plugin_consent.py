import json
from pathlib import Path
import tempfile
import unittest

from neuro_rt import plugin_consent as consent


class PluginConsentTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / 'runtime/test-tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.config = Path(self.tmp.name) / 'config'

    def accept(self, stage='installation', **changes):
        policy = consent.policy()
        payload = dict(accepted=True, version=policy['version'], digest=policy['digest'])
        payload.update(changes)
        return consent.accept(self.config, stage, payload)

    def test_installation_and_first_use_are_distinct_explicit_acts(self):
        self.assertFalse(consent.accepted(self.config, 'installation'))
        receipt = self.accept()
        self.assertTrue(consent.accepted(self.config, 'installation'))
        self.assertFalse(consent.accepted(self.config, 'first_use'))
        self.assertEqual(self.accept('first_use')['digest'], receipt['digest'])
        self.assertTrue(consent.accepted(self.config, 'first_use'))
        self.assertNotIn('patient', json.dumps(receipt))
        self.assertNotIn('operator', json.dumps(receipt))

    def test_mismatched_or_unchecked_acknowledgement_writes_nothing(self):
        for changes in ({'accepted': False}, {'accepted': 1}, {'version': 'old'}, {'digest': '0'*64}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.accept(**changes)
        self.assertFalse(self.config.exists())

    def test_corrupt_or_stale_receipt_cannot_unlock(self):
        self.accept('first_use')
        path = self.config / 'consent-first_use.json'
        receipt = json.loads(path.read_text(encoding='utf-8'))
        receipt['digest'] = '0'*64
        path.write_text(json.dumps(receipt), encoding='utf-8')
        self.assertFalse(consent.accepted(self.config, 'first_use'))
        path.write_text('invalid json', encoding='utf-8')
        self.assertFalse(consent.accepted(self.config, 'first_use'))

    def test_policy_keeps_boundaries_and_does_not_replace_component_licenses(self):
        text = json.dumps(consent.policy(), ensure_ascii=False)
        for term in ('Nidus', 'UNAPPROVED', 'TPS', 'MIT', 'Apache', 'licenças', 'interseção', 'fase de testes'):
            self.assertIn(term, text)
        self.assertEqual(consent.policy()['digest'], consent.policy()['digest'])


if __name__ == '__main__':
    unittest.main()

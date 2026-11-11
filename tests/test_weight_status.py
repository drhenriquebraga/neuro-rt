"""Weight status is independent of the code release and version check."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import test_resource_only_install as fixture
from neuro_rt import resource_status


class WeightStatusTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.ResourceOnlyTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.plugin = self.fixture.plugin
        self.code = self.plugin / 'versions/1.3.2'

    def state(self):
        return json.loads(self.fixture.pointer.read_text())

    def test_current_code_without_models_reports_weights_missing(self):
        status = resource_status.inspect_weights(self.plugin, self.code, self.state())
        self.assertEqual(status['state'], 'missing')
        self.assertIsNone(status['version'])
        self.assertEqual(len(status['recipe_sha256']), 64)
        self.assertEqual(status['missing_components'], ['extras'])

    def test_offline_weights_keep_their_bundle_version_separate_from_code(self):
        with patch.object(fixture.external, '_prepare_resources', side_effect=self.fixture.prepare_resources):
            self.fixture.run_plan(self.fixture.resource_plan())
        state = self.state()
        self.assertEqual(state['active_version'], '1.3.2')
        status = resource_status.inspect_weights(self.plugin, self.code, state)
        self.assertEqual(status['state'], 'ready')
        self.assertEqual(status['version'], '1.3.0')
        self.assertFalse(status['missing_components'])
        state.pop('resource_bundle_version')
        self.assertIsNone(resource_status.inspect_weights(self.plugin, self.code, state)['version'])

    def test_partial_model_and_missing_extras_are_not_reported_as_updated_ready(self):
        recipe_file = self.code / 'catalog/resource_recipe.json'
        recipe_file.write_text(json.dumps({'models': [{'id': 'synthetic', 'revision': 'rev1',
            'files': {'weight.bin': {'size': 6, 'sha256': '0' * 64}}}]}))
        file = self.plugin / 'models/synthetic/rev1/weight.bin'
        file.parent.mkdir(parents=True)
        file.write_bytes(b'bad')
        status = resource_status.inspect_weights(self.plugin, self.code, self.state())
        self.assertEqual(status['state'], 'partial')
        self.assertEqual(status['missing_components'], ['extras', 'synthetic'])


if __name__ == '__main__':
    unittest.main()

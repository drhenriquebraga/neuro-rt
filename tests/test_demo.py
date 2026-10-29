import json
import tempfile
import unittest
from pathlib import Path

from neuro_rt.service import Service, Settings
from test_pipeline import TEMP_ROOT


class DemoTests(unittest.TestCase):
    def test_demo_cache_survives_restart_and_never_starts_inference(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            job_id = 'd' * 32
            job = root / 'runtime/jobs' / job_id
            job.mkdir(parents=True)
            result = {'schema': 'neuro-rt/result/1', 'model_id': 'MRI_GBM',
                      'backend_version': 'test', 'status': 'completed',
                      'masks': [], 'approval_status': 'UNAPPROVED',
                      'visualization': {'available': True}}
            (job / 'manifest.json').write_text(json.dumps(result))
            cache = root / 'runtime/demos.json'
            cache.write_text(json.dumps({'schema': 'neuro-rt/demos/1', 'demos': [
                {'model': 'MRI_LGGlioma', 'job_id': 'e' * 32, 'label': 'ausente'},
                {'model': 'MRI_GBM', 'job_id': job_id, 'label': 'Demo pública',
                 'source_url': 'https://example.org', 'license': 'CC0'}]}))
            service = Service(Settings(root))
            demo = service.demo('MRI_GBM')
            self.assertEqual(demo['result']['model_id'], 'MRI_GBM')
            self.assertEqual(demo['demo']['license'], 'CC0')
            self.assertIsNone(service._process)
            self.assertIsNone(service._thread)
            self.assertEqual(service.status()['demos'][0]['model'], 'MRI_GBM')
            with self.assertRaises(KeyError):
                service.demo('MRI_Meningioma')

    def test_cache_path_and_model_mismatch_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            (root / 'runtime').mkdir()
            (root / 'runtime/demos.json').write_text(json.dumps({
                'schema': 'neuro-rt/demos/1', 'demos': [
                    {'model': 'MRI_GBM', 'job_id': '../outside', 'label': 'bad'}]}))
            service = Service(Settings(root))
            self.assertEqual(service.status()['demos'], [])


if __name__ == '__main__':
    unittest.main()

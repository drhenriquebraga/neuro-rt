import json
import tempfile
import time
import unittest
from pathlib import Path

from neuro_rt.service import Service, Settings
from test_pipeline import TEMP_ROOT


class ServiceTests(unittest.TestCase):
    def test_no_job_created_without_explicit_request(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service = Service(Settings(Path(tmp)))
            with self.assertRaises(ValueError):
                service.submit({'model': 'MRI_GBM', 'input_path': 'x'})
            self.assertFalse((Path(tmp) / 'runtime' / 'jobs').exists())

    def test_artifact_cannot_escape_job_folder(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service = Service(Settings(Path(tmp)))
            for name in ('../secret', '/absolute', 'nested/mask.nii.gz'):
                with self.assertRaises(ValueError):
                    service.artifact('x', name)

    def test_errors_do_not_report_completed_and_process_can_run_again(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            service = Service(Settings(root))
            service.preflight = lambda request: None
            service.worker_command = lambda request, job_dir: [service.settings.python, '-c', 'raise RuntimeError("synthetic")']
            request = {'model': 'MRI_GBM', 'input_path': str(root), 'explicit_request': True}
            job = service.submit(request)
            for _ in range(100):
                state = service.job(job['id'])
                if state['status'] == 'failed':
                    break
                time.sleep(.02)
            self.assertEqual(state['status'], 'failed')
            self.assertNotIn('result', state)
            self.assertTrue((root / 'runtime' / 'jobs' / job['id'] / 'worker.log').exists())
            another = service.submit(request)
            self.assertNotEqual(another['id'], job['id'])
            service.close()

    def test_local_config_resolves_relative_paths_for_relocation(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            (root / 'neuro_rt.local.json').write_text(json.dumps({'models_dir': 'weights', 'data_dir': 'jobs'}))
            settings = Settings(root)
            self.assertEqual(settings.models_dir, root / 'weights')
            self.assertEqual(settings.data_dir, root / 'jobs')


if __name__ == '__main__':
    unittest.main()

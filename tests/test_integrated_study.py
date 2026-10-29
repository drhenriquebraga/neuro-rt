"""HTTP + real host reader/writer/viewers; model boundary is a known phantom ROI."""
import importlib.util
import tempfile
import time
from pathlib import Path
import unittest
from unittest.mock import patch

from synthetic_dicom import make_series
from test_pipeline import TEMP_ROOT
from test_study_service import Bridge

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT.parent / 'AUTO_CONTORNO'


@unittest.skipUnless(importlib.util.find_spec('fastapi') and importlib.util.find_spec('httpx'),
                     'Executar pelo Python do Local Suite com FastAPI/httpx.')
class IntegratedStudyTests(unittest.TestCase):
    def test_ticket_to_one_rtstruct_then_reopen_authorized_mpr_and_history(self):
        import numpy as np
        import SimpleITK as sitk
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from integration.host_imports import prepare_host_imports
        from integration.default_host_services import bindings_for_host
        from integration.host_services import build_host_services
        from integration.radai_neuro import montar
        from neuro_rt.service import Settings
        from neuro_rt.study_types import ModelResult, MaskArtifact
        from neuro_rt.imaging import geometry
        prepare_host_imports(HOST)
        import radai_dicom
        import radai_thumbnail
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            directory = Path(temporary)
            source = directory / 'original'
            uid, _ = make_series(source)
            ticket = radai_thumbnail.registrar_series(str(source),
                radai_dicom.varrer(str(source))['series'])[uid]
            bridge = Bridge()
            bindings = bindings_for_host({'suite_root': str(HOST)})
            bindings.update(queue_bridge=bridge, register_result=lambda receipt: None)
            services = build_host_services({'suite_root': str(HOST), 'version': '8.10'}, bindings)
            settings = Settings(ROOT)
            settings.data_dir = directory / 'data'
            app = FastAPI()
            with patch('neuro_rt.service.Settings', return_value=settings):
                service = montar(app, ROOT, host_services=services)
            def phantom(spec, context, event):
                image = sitk.ReadImage(str(context.authorized_inputs[context.reference.ticket]))
                bits = np.zeros(tuple(reversed(image.GetSize())), np.uint8)
                bits[2:5, 5:10, 7:11] = 1
                bits[2:5, 1:4, 1:4] = 1
                mask = sitk.GetImageFromArray(bits); mask.CopyInformation(image)
                context.job_dir.mkdir(parents=True, exist_ok=True)
                output = context.job_dir / 'phantom.nii.gz'; sitk.WriteImage(mask, str(output))
                return ModelResult(spec['id'], 'completed', [MaskArtifact(
                    spec['id'], 'tumor', str(output), geometry(image))])
            service.studies.run_model = phantom
            with TestClient(app) as client:
                token = client.get('/neuro/api/status').json()['token']
                headers = {'X-Neuro-Token': token, 'Origin': 'http://testserver'}
                payload = {'schema': 'neuro-rt/request/2', 'explicit_request': True,
                    'request_id': 'integrated', 'export_rtstruct': True,
                    'studies': [{'study_id': 'integrated', 'reference': ticket,
                        'model_ids': ['MRI_GBM'], 'bindings_by_model': {
                            'MRI_GBM': [{'role': 'T1c', 'series_ticket': ticket,
                                         'certainty': 'uncertain'}]}}]}
                response = client.post('/neuro/api/studies', json=payload, headers=headers)
                self.assertEqual(response.status_code, 202, response.text)
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    job = client.get('/neuro/api/studies/integrated').json()
                    if job['status'] in ('completed', 'partial', 'failed', 'cancelled'): break
                    time.sleep(.1)
                log = settings.data_dir / 'jobs/integrated/export.log'
                details = log.read_text(encoding='utf-8', errors='replace') if log.is_file() else job['message']
                if job['status'] != 'completed':
                    import shutil
                    debug = ROOT / 'runtime' / ('integrated-debug-' + str(time.time_ns()))
                    shutil.copytree(directory, debug)
                    details += '\nSynthetic diagnostic: ' + str(debug)
                self.assertEqual(job['status'], 'completed', details)
                self.assertEqual(len(list(source.glob('RS_NeuroRT_*.dcm'))), 1)
                result = job['result']
                self.assertEqual(result['export_status'], 'completed')
                self.assertEqual(result['approval_status'], 'UNAPPROVED')
                view = next(a for a in result['artifacts'] if a.get('logical_name') == 'view.json')
                response = client.get('/neuro/api/studies/integrated/artifacts/' + view['artifact_id'])
                self.assertEqual(response.status_code, 200)
                self.assertIn('planes', response.json())
                history = client.get('/neuro/api/studies/integrated?revision=1').json()
                self.assertEqual(history['result']['revision'], 1)
                self.assertEqual(client.get('/neuro/api/studies/integrated/artifacts/invalid').status_code, 400)
                self.assertNotIn(str(directory), str(result))
                self.assertEqual(bridge.finished, ['completed'])

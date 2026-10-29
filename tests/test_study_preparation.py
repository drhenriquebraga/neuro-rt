import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import SimpleITK as sitk
from pydicom.dataset import Dataset

from neuro_rt.study_types import SeriesDescriptor
from neuro_rt.study_service import atomic_json
from neuro_rt.study_worker import prepare
from test_pipeline import TEMP_ROOT


class StudyPreparationTests(unittest.TestCase):
    def scenario(self, root, failure=None, header_change=None, transform=None):
        records, headers = {}, {}
        for number, ticket in enumerate(('ref', 'bad', 'good'), 1):
            uid = f'1.2.{number}'
            files = []
            for slice_index in range(2):
                path = root / f'{ticket}_{slice_index}.dcm'; path.write_bytes(b'synthetic')
                files.append(str(path))
                ds = Dataset()
                ds.SeriesInstanceUID, ds.FrameOfReferenceUID = uid, '1.9'
                ds.SOPInstanceUID = f'{uid}.{slice_index}'
                ds.PatientID, ds.StudyInstanceUID, ds.Modality = 'SYNTH', '1.8', 'MR'
                ds.ImagePositionPatient = [0, 0, slice_index]
                ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
                ds.PixelSpacing, ds.Rows, ds.Columns = [1, 1], 2, 2
                if header_change: header_change(ticket, slice_index, ds)
                headers[str(path)] = ds
            descriptor = SeriesDescriptor(ticket, uid, 'subject', 'study', 'MR',
                frame_of_reference_uid='1.9', sop_instance_uids=[f'{uid}.0', f'{uid}.1'])
            records[ticket] = {**descriptor.to_dict(), 'source': {
                'input_path': ticket, 'dicom_files': files, 'kind': 'dicom'}}
        atomic_json(root / 'input-sources.json', {'reference': 'ref', 'host_app': str(root), 'sources': records})
        def load(folder, uid):
            if folder == failure: raise RuntimeError('private synthetic load failure')
            return sitk.Image([2, 2, 2], sitk.sitkFloat32)
        registrations = []
        class Registration:
            REGULAR = 1
            def __getattr__(self, name): return lambda *args, **kwargs: None
            def Execute(self, fixed, moving):
                registrations.append(True)
                if failure == 'registration' or failure == 'bad_registration' and len(registrations) == 1:
                    raise RuntimeError('private registration failure')
                return transform if transform is not None else sitk.Transform(3, sitk.sitkIdentity)
            def GetMetricValue(self): return 1.
        return patch.multiple('integration.host_imports', prepare_host_imports=lambda _: None), patch.dict(
            sys.modules, {'engine': SimpleNamespace(load_sitk=load)}), patch(
            'pydicom.dcmread', side_effect=lambda path, **kwargs: headers[str(path)]), patch(
            'SimpleITK.ImageRegistrationMethod', Registration)

    def prepared(self, root, **kwargs):
        host, engine, reader, registration = self.scenario(root, **kwargs)
        with host, engine, reader, registration: prepare(root)
        return json.loads((root / 'prepared-inputs.json').read_text(encoding='utf-8'))

    def test_channel_load_failure_keeps_authorized_index_and_independent_inputs(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp); data = self.prepared(root, failure='bad')
            self.assertEqual(set(data['series_index']), {'ref', 'bad', 'good'})
            self.assertEqual(set(data['authorized_inputs']), {'ref', 'good'})
            self.assertEqual(set(data['source_to_reference']), {'good'})
            errors = json.loads((root / 'preparation-errors.json').read_text(encoding='utf-8'))
            self.assertIn('private synthetic load failure', str(errors))
            self.assertNotIn('private synthetic', str(data))

    def test_registration_failure_does_not_remove_reference_input(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            data = self.prepared(Path(tmp), failure='registration')
            self.assertEqual(set(data['authorized_inputs']), {'ref', 'bad', 'good'})
            self.assertEqual(data['source_to_reference'], {})

    def test_failed_registration_continues_independent_channel(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            data = self.prepared(Path(tmp), failure='bad_registration')
            self.assertEqual(set(data['authorized_inputs']), {'ref', 'bad', 'good'})
            self.assertEqual(set(data['source_to_reference']), {'good'})

    def test_reference_load_failure_is_fatal(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            with self.assertRaises(RuntimeError): self.prepared(Path(tmp), failure='ref')

    def test_header_nan_and_patient_mix_are_not_accepted(self):
        for change in ('nan', 'patient', 'cross_series_patient'):
            with self.subTest(change=change), tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
                def modify(ticket, n, ds):
                    if ticket == 'bad' and (n == 1 or change == 'cross_series_patient'):
                        if change == 'nan': ds.ImagePositionPatient = [0, 0, float('nan')]
                        else: ds.PatientID = 'OTHER_SYNTH'
                data = self.prepared(Path(tmp), header_change=modify)
                self.assertNotIn('bad', data['authorized_inputs'])
                self.assertIn('good', data['authorized_inputs'])

    def test_nonfinite_composite_transform_is_not_saved(self):
        transform = sitk.TranslationTransform(3)
        transform.SetOffset([float('nan'), 0, 0])
        composite = sitk.CompositeTransform(3); composite.AddTransform(transform)
        composite.AddTransform(sitk.Euler3DTransform())
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            data = self.prepared(Path(tmp), transform=composite)
            self.assertEqual(data['source_to_reference'], {})

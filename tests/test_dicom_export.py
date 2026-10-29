import json
import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pydicom
import SimpleITK as sitk

from neuro_rt.imaging import load_input, geometry
from neuro_rt.export import verify_rtstruct
from synthetic_dicom import make_series
from test_pipeline import TEMP_ROOT


class DicomTests(unittest.TestCase):
    def test_multiple_series_require_uid_and_ct_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            folder = Path(tmp) / 'dicom'
            uid, frame = make_series(folder)
            make_series(folder, z_offset=200)
            with self.assertRaises(ValueError):
                load_input(folder)
            image, source = load_input(folder, uid)
            self.assertEqual(source['frame_uid'], frame)
            self.assertEqual(image.GetOrigin(), (20., 30., 0.))
            ct = Path(tmp) / 'ct'
            make_series(ct, modality='CT')
            with self.assertRaises(ValueError):
                load_input(ct)

    def test_irregular_slices_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            make_series(tmp)
            file = sorted(Path(tmp).glob('*.dcm'))[3]
            ds = pydicom.dcmread(file)
            ds.ImagePositionPatient = [20., 30., 6.4]
            ds.save_as(file, enforce_file_format=True)
            with self.assertRaises(ValueError):
                load_input(tmp)

    def test_host_writer_emits_unapproved_original_frame(self):
        config = Path(__file__).resolve().parents[1] / 'neuro_rt.local.json'
        if not config.is_file():
            self.skipTest('Host não configurado para teste de integração.')
        settings = json.loads(config.read_text())
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            job = Path(tmp)
            uid, frame = make_series(job / 'dicom_source')
            shutil.copytree(job/'dicom_source', job/'original_source')
            image, source = load_input(job / 'dicom_source', uid)
            array = np.zeros((8, 16, 16), dtype=np.uint8)
            array[2:5, 5:10, 7:11] = 1
            array[2:5, 1:4, 1:4] = 1
            mask = sitk.GetImageFromArray(array)
            mask.CopyInformation(image)
            (job / 'masks').mkdir()
            sitk.WriteImage(mask, str(job / 'masks/Tumor.nii.gz'))
            manifest = {'schema':'neuro-rt/result/1','model_id':'MRI_GBM', 'model_release':'1.2.0',
                        'approval_status':'UNAPPROVED','geometry':geometry(image),'status':'completed',
                        'source':{**{k:v for k,v in source.items() if k != 'dicom_files'},
                                  'input_path':str(job/'original_source')},
                        'masks':[{'path':'masks/Tumor.nii.gz','roi_name':'Tumor_NeuroRT','voxels':87}]}
            (job / 'manifest.json').write_text(json.dumps(manifest))
            script = Path(__file__).parent / 'host_export_scenario.py'
            run = subprocess.run([settings['host_python'], str(script), str(job),
                                  settings['host_app']], capture_output=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stderr.decode(errors='replace')[-1500:])
            result = verify_rtstruct(job / 'RS_NeuroRT.dcm', source)
            self.assertEqual(result['approval_status'], 'UNAPPROVED')
            self.assertEqual(result['frame_uid'], frame)
            self.assertEqual(len(result['roi_names']), 1)
            published=json.loads((job/'manifest.json').read_text())['rtstruct']['source_path']
            self.assertEqual(Path(published).parent,job/'original_source')
            self.assertTrue(Path(published).is_file())
            ds = pydicom.dcmread(job / 'RS_NeuroRT.dcm')
            points = np.concatenate([np.array(c.ContourData).reshape(-1,3)
                                     for roi in ds.ROIContourSequence for c in roi.ContourSequence])
            self.assertEqual(sorted(set(points[:,2])), [4.,6.,8.])
            self.assertLess(points[:,0].min(), 24.)
            self.assertGreater(points[:,0].max(), 26.)
            self.assertEqual(len(list((job/'original_source').glob('RS_NeuroRT_*.dcm'))), 2)
            ds.ApprovalStatus = 'APPROVED'
            ds.save_as(job / 'bad.dcm', enforce_file_format=True)
            with self.assertRaises(ValueError):
                verify_rtstruct(job / 'bad.dcm', source)


if __name__ == '__main__':
    unittest.main()

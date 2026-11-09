import configparser
import tempfile
import unittest
from pathlib import Path

import numpy as np
import SimpleITK as sitk

from neuro_rt.catalog import get_model, validate_model_folder
from neuro_rt.contracts import validate_request
from neuro_rt.imaging import validate_mask, load_input
from neuro_rt.worker import write_runtime_config

TEMP_ROOT = Path(__file__).resolve().parents[1] / '.research' / 'test_tmp'
TEMP_ROOT.mkdir(parents=True, exist_ok=True)


class PipelineTests(unittest.TestCase):
    def test_finding_requires_explicit_true_not_truthy_string(self):
        for value in (False, None, 'true', 1):
            with self.assertRaises(ValueError):
                validate_request({'model': 'MRI_GBM', 'input_path': 'x',
                                  'explicit_request': value})

    def test_unknown_model_is_not_run(self):
        with self.assertRaises(ValueError):
            get_model('MRI_Glioblastoma')

    def test_paths_and_device_are_required_and_validated(self):
        for override in ({'input_path': ''}, {'device': 'automatic'},
                         {'export_rtstruct': 'yes'}):
            request = {'model': 'MRI_GBM', 'input_path': 'volume.nii.gz',
                       'explicit_request': True, **override}
            with self.assertRaises(ValueError):
                validate_request(request)

    def test_empty_and_binary_masks_preserve_oblique_geometry(self):
        ref = sitk.Image([15, 13, 9], sitk.sitkFloat32)
        ref.SetSpacing((0.8, 1.7, 3.1))
        ref.SetOrigin((40., -30., 15.))
        ref.SetDirection((0., -1., 0., 1., 0., 0., 0., 0., 1.))
        array = np.zeros((9, 13, 15), dtype=np.uint8)
        array[2:4, 5:7, 9:11] = 1
        image = sitk.GetImageFromArray(array)
        image.CopyInformation(ref)
        mask = validate_mask(image, ref)
        self.assertEqual(mask['voxels'], 8)
        self.assertAlmostEqual(mask['volume_cm3'], 8 * .8 * 1.7 * 3.1 / 1000)
        image = sitk.Image(ref.GetSize(), sitk.sitkUInt8)
        image.CopyInformation(ref)
        self.assertEqual(validate_mask(image, ref)['voxels'], 0)

    def test_same_shape_wrong_origin_or_probability_is_rejected(self):
        ref = sitk.Image([6, 8, 9], sitk.sitkFloat32)
        image = sitk.Image(ref)
        image.SetOrigin((1., 0., 0.))
        with self.assertRaises(ValueError):
            validate_mask(image, ref)
        image = sitk.Image(ref) + .4
        with self.assertRaises(ValueError):
            validate_mask(image, ref)

    def test_nifti_loading_is_scalar_3d_and_ct_cannot_be_assumed_mr(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            path = Path(tmp) / 'input.nii.gz'
            sitk.WriteImage(sitk.Image([6, 7, 8], sitk.sitkFloat32), str(path))
            image, source = load_input(path, '')
            self.assertEqual(image.GetSize(), (6, 7, 8))
            self.assertEqual(source['kind'], 'nifti')
            self.assertFalse(source['dicom_files'])

    def test_runtime_uses_official_sections_and_explicit_local_model(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            path = write_runtime_config(Path(tmp), Path(tmp) / 'weights', 'cpu')
            cfg = configparser.ConfigParser()
            cfg.read(path)
            self.assertEqual(cfg['System']['gpu_id'], '-1')
            self.assertEqual(cfg['System']['model_folder'], str(Path(tmp) / 'weights'))
            self.assertEqual(cfg['Runtime']['reconstruction_method'], 'thresholding')
            self.assertFalse(cfg.has_option('Runtime', 'model_name'))

    def test_incomplete_weights_cannot_be_marked_ready(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            with self.assertRaises(ValueError):
                validate_model_folder(Path(tmp), get_model('MRI_GBM'))


if __name__ == '__main__':
    unittest.main()

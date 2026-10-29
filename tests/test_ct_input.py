from pathlib import Path
import tempfile
import unittest

from neuro_rt.imaging import dicom_series, load_input
from synthetic_dicom import make_series
from test_pipeline import TEMP_ROOT


class CTInputTests(unittest.TestCase):
    def test_ct_is_explicit_for_new_path_and_rejected_by_legacy_mr_default(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            uid, frame = make_series(tmp, modality='CT')
            self.assertEqual(dicom_series(tmp), [])
            with self.assertRaises(ValueError): load_input(tmp, uid)
            image, source = load_input(tmp, uid, allowed_modalities=('CT',))
            self.assertEqual(image.GetSize(), (16, 16, 8))
            self.assertEqual(source['modality'], 'CT')
            self.assertEqual(source['frame_uid'], frame)

    def test_mixed_modality_in_same_series_is_rejected(self):
        import pydicom
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            uid, _ = make_series(tmp, modality='CT')
            file = sorted(Path(tmp).glob('*.dcm'))[-1]
            header = pydicom.dcmread(file); header.Modality = 'MR'
            header.save_as(file, enforce_file_format=True)
            with self.assertRaises(ValueError):
                load_input(tmp, uid, allowed_modalities=('CT',))

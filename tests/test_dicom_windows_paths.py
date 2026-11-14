"""The host supplies extended Windows paths; GDCM needs its native spelling."""
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np
import SimpleITK as sitk
from neuro_rt.imaging import load_input, dicom_file_identity
from synthetic_dicom import make_series
from test_pipeline import TEMP_ROOT


@unittest.skipUnless(os.name == 'nt', 'Windows extended-path regression')
class DicomWindowsPaths(unittest.TestCase):
    def test_host_extended_path_retains_series_and_voxels(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as folder:
            uid, _ = make_series(Path(folder))
            plain, plain_source = load_input(folder, uid)
            extended, source = load_input('\\\\?\\' + str(Path(folder).resolve()), uid)
            self.assertEqual(source['series_uid'], uid)
            self.assertEqual(set(source['sop_uids']), set(plain_source['sop_uids']))
            self.assertEqual(extended.GetOrigin(), plain.GetOrigin())
            self.assertEqual(extended.GetDirection(), plain.GetDirection())
            np.testing.assert_array_equal(sitk.GetArrayFromImage(extended), sitk.GetArrayFromImage(plain))
            self.assertEqual({dicom_file_identity(f) for f in source['dicom_files']},
                             {dicom_file_identity('\\\\?\\' + f) for f in plain_source['dicom_files']})


if __name__ == '__main__': unittest.main()

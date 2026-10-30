import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import threading

import numpy as np
import SimpleITK as sitk

from neuro_rt.scientific_io import (enable_private_worker_io, read_image, write_image,
                                    read_transform, write_transform, native_file_path)
from neuro_rt.geometry_pipeline import _validate_transform, _inverse_transform

TEMP = Path(__file__).resolve().parents[1] / '.research/test_tmp'
TEMP.mkdir(parents=True, exist_ok=True)


class ScientificIOTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Restrição de I/O nativo Windows.')
    def test_unicode_cwd_is_refused_outside_owned_child_or_main_thread(self):
        import neuro_rt.scientific_io as io
        original = Path.cwd()
        path = TEMP / 'Pasta sintética' / 'reference.nii.gz'
        with patch.object(io, '_private_worker', False):
            with self.assertRaises(RuntimeError): read_image(path)
        errors = []
        def attempt():
            try: read_image(path)
            except RuntimeError: errors.append(True)
        enable_private_worker_io()
        worker = threading.Thread(target=attempt); worker.start(); worker.join()
        self.assertEqual(errors, [True])
        self.assertEqual(Path.cwd(), original)

    def test_ants_unicode_image_roundtrip_when_runtime_provides_ants(self):
        try: import ants
        except ImportError: self.skipTest('ANTs ausente neste runtime do host.')
        enable_private_worker_io()
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            folder = Path(tmp) / 'Atlas sintético com acento'; folder.mkdir()
            array = np.arange(4 * 5 * 6, dtype=np.float32).reshape(4, 5, 6)
            angle = .23
            direction = np.array([[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]])
            image = ants.from_numpy(array, origin=(12., -8., 4.), spacing=(.8, 1.2, 2.3), direction=direction)
            path = folder / 'ants.nii.gz'
            original_cwd = Path.cwd()
            with native_file_path(path) as local: ants.image_write(image, local)
            with native_file_path(path) as local: loaded = ants.image_read(local)
            np.testing.assert_array_equal(loaded.numpy(), array)
            np.testing.assert_allclose(loaded.direction, direction, atol=1e-6)
            np.testing.assert_allclose(loaded.origin, image.origin, atol=1e-6)
            np.testing.assert_allclose(loaded.spacing, image.spacing, atol=1e-6)
            self.assertEqual(Path.cwd(), original_cwd)

    def test_unicode_nifti_roundtrip_preserves_voxels_and_oblique_physical_grid(self):
        enable_private_worker_io()
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            folder = Path(tmp) / 'Suíte sintética rotação'; folder.mkdir()
            original_cwd = Path.cwd()
            array = np.arange(7 * 8 * 9, dtype=np.float32).reshape(7, 8, 9)
            image = sitk.GetImageFromArray(array)
            image.SetSpacing((.8, 1.2, 2.3)); image.SetOrigin((12., -8., 4.))
            angle = .31
            image.SetDirection((np.cos(angle), -np.sin(angle), 0, np.sin(angle), np.cos(angle), 0, 0, 0, 1))
            for suffix in ('.nii', '.nii.gz'):
                path = folder / ('roundtrip' + suffix)
                write_image(image, path)
                loaded = read_image(path)
                np.testing.assert_array_equal(sitk.GetArrayFromImage(loaded), array)
                for getter in ('GetSize', 'GetSpacing', 'GetOrigin', 'GetDirection'):
                    np.testing.assert_allclose(getattr(image, getter)(), getattr(loaded, getter)(), atol=1e-6)
            self.assertEqual(Path.cwd(), original_cwd)
            with self.assertRaises(RuntimeError): read_image(folder / 'missing.nii.gz')
            self.assertEqual(Path.cwd(), original_cwd)

    def test_rigid_composition_inverse_roundtrip_keeps_physical_points(self):
        enable_private_worker_io()
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            folder = Path(tmp) / 'Transformações sintéticas'; folder.mkdir()
            rigid = sitk.Euler3DTransform(); rigid.SetCenter((13., -8., 5.))
            rigid.SetRotation(.17, -.12, .23); rigid.SetTranslation((3., -2., 1.))
            transform = sitk.CompositeTransform(3)
            transform.AddTransform(rigid)
            transform.AddTransform(sitk.TranslationTransform(3, (1., 2., -3.)))
            inverse = _inverse_transform(transform, 3)
            path = folder / 'inverse.tfm'; write_transform(inverse, path)
            loaded = read_transform(path); _validate_transform(loaded, 3)
            restored = _inverse_transform(loaded, 3)
            for point in ((0., 0., 0.), (13., -8., 5.), (-17., 21., 8.), (9., 10., -4.)):
                np.testing.assert_allclose(loaded.TransformPoint(transform.TransformPoint(point)), point, atol=1e-10)
                np.testing.assert_allclose(restored.TransformPoint(point), transform.TransformPoint(point), atol=1e-10)
            bad = sitk.TranslationTransform(3, (float('nan'), 0, 0))
            transform.AddTransform(bad)
            with self.assertRaises(ValueError): _inverse_transform(transform, 3)

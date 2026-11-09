"""Physical-space tests, using asymmetric synthetic images only."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import SimpleITK as sitk

from neuro_rt.adapters.base import ModelRunContext
from neuro_rt.geometry_pipeline import (prepare_model_inputs, restore_masks,
                                        verify_reference_geometry)
from neuro_rt.imaging import geometry
from neuro_rt.study_types import InputBinding, MaskArtifact, ModelResult, SeriesDescriptor
from test_pipeline import TEMP_ROOT


class ReferenceGeometryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.array = np.zeros((7, 9, 11), np.float32)
        self.array[1, 2, 9] = 1
        self.array[5, 7, 1] = 1
        self.image = sitk.GetImageFromArray(self.array)
        angle = np.deg2rad(23)
        self.image.SetDirection((np.cos(angle), -np.sin(angle), 0,
                                 np.sin(angle), np.cos(angle), 0, 0, 0, 1))
        self.image.SetSpacing((.7, 1.3, 2.1))
        self.image.SetOrigin((31, -47, 19))
        self.path = self.root / 'reference.nii.gz'
        sitk.WriteImage(self.image, str(self.path))
        self.ref = SeriesDescriptor('ref', '', 'subject', 'study', 'MR',
                                    geometry(self.image), source_format='nifti')
        self.spec = {'id': 'MRI_GBM', 'channels': [{'role': 'T1c'}],
                     'classes': [{'class_id': 'tumor', 'label': 'Tumor'}]}
        self.context = ModelRunContext(self.spec, [InputBinding('T1c', 'ref')], self.ref,
                                      {'ref': self.ref}, {'ref': self.path},
                                      self.root / 'job', self.root / 'models', 'cpu')

    def test_same_shape_shifted_or_flipped_mask_fails_geometry_verification(self):
        self.assertTrue(verify_reference_geometry(self.image, self.ref).valid)
        shifted = sitk.Image(self.image)
        shifted.SetOrigin((32, -47, 19))
        self.assertFalse(verify_reference_geometry(shifted, self.ref).valid)
        flipped = sitk.Image(self.image)
        flipped.SetDirection(tuple(-v for v in self.image.GetDirection()))
        self.assertFalse(verify_reference_geometry(flipped, self.ref).valid)

    def test_roundtrip_preserves_oblique_anisotropic_foci_and_separate_classes(self):
        prepared = prepare_model_inputs(self.context.bindings, self.ref, self.spec, self.context)
        mask_path = self.root / 'mask.nii.gz'
        sitk.WriteImage(sitk.Cast(self.image, sitk.sitkUInt8), str(mask_path))
        result = ModelResult('MRI_GBM', 'completed', [
            MaskArtifact('MRI_GBM', key, str(mask_path), geometry(self.image), 'working')
            for key in ('tumor', 'nested')])
        restored = restore_masks(result, prepared, self.ref)
        self.assertEqual([m.class_id for m in restored], ['tumor', 'nested'])
        for artifact in restored:
            output = sitk.ReadImage(artifact.path)
            np.testing.assert_array_equal(sitk.GetArrayFromImage(output), self.array)
            self.assertTrue(verify_reference_geometry(output, self.ref).valid)
            np.testing.assert_allclose(output.TransformIndexToPhysicalPoint((9, 2, 1)),
                sitk.ReadImage(str(self.path)).TransformIndexToPhysicalPoint((9, 2, 1)), atol=1e-5, rtol=0)

    def test_different_series_requires_explicit_registration_even_if_grid_equal(self):
        other = SeriesDescriptor('other', '', 'subject', 'study', 'MR',
                                  geometry(self.image), source_format='nifti')
        self.context.series_index['other'] = other
        self.context.authorized_inputs['other'] = self.path
        with self.assertRaisesRegex(ValueError, 'registro'):
            prepare_model_inputs([InputBinding('T1c', 'other')], self.ref,
                                 self.spec, self.context)

    def test_explicit_lps_registration_moves_asymmetric_landmarks_physically(self):
        # Source origin is translated; source->reference transform undoes it.
        moved = sitk.Image(self.image)
        moved.SetOrigin((35, -50, 21))
        source_path = self.root / 'source.nii.gz'
        sitk.WriteImage(moved, str(source_path))
        other = SeriesDescriptor('other', '', 'subject', 'study', 'MR',
                                  geometry(moved), source_format='nifti')
        self.context.series_index['other'] = other
        self.context.authorized_inputs['other'] = source_path
        transform = sitk.TranslationTransform(3, (-4, 3, -2))
        transform_path = self.root / 'registration.tfm'
        sitk.WriteTransform(transform, str(transform_path))
        self.context.source_to_reference['other'] = transform_path
        prepared = prepare_model_inputs([InputBinding('T1c', 'other')], self.ref,
                                        self.spec, self.context)
        np.testing.assert_allclose(sitk.GetArrayFromImage(sitk.ReadImage(
            prepared.channel_paths[0])), self.array, atol=1e-5)
        self.assertEqual(prepared.transform_chain[0]['transform_path'], str(transform_path))

    def test_nonfinite_registration_cannot_silently_erase_a_channel(self):
        other = SeriesDescriptor('other', '', 'subject', 'study', 'MR',
                                  geometry(self.image), source_format='nifti')
        self.context.series_index['other'] = other
        self.context.authorized_inputs['other'] = self.path
        nan_translation = sitk.TranslationTransform(3, (float('nan'), 0, 0))
        nan_center = sitk.AffineTransform(3)
        nan_center.SetCenter((float('nan'), 0, 0))
        composite = sitk.CompositeTransform(3)
        composite.AddTransform(nan_translation)
        composite.AddTransform(sitk.TranslationTransform(3))
        overflowing_inverse = sitk.AffineTransform(3)
        overflowing_inverse.Scale((.5, 1, 1))
        overflowing_inverse.SetTranslation((1e308, 0, 0))
        composite_inverse = sitk.CompositeTransform(3)
        composite_inverse.AddTransform(sitk.TranslationTransform(3))
        composite_inverse.AddTransform(overflowing_inverse)
        cases = {'translation_nan': nan_translation, 'fixed_center_nan': nan_center,
                 'hidden_composite_nan': composite, 'inverse_overflow': overflowing_inverse,
                 'hidden_inverse_composite_overflow': composite_inverse,
                 'wrong_dimension': sitk.TranslationTransform(2)}
        for name, transform in cases.items():
            with self.subTest(name=name):
                # Binary transform storage preserves NaN; the text .tfm parser
                # rejects its spelling before reaching the numerical boundary.
                path = self.root / (name + '.h5')
                sitk.WriteTransform(transform, str(path))
                self.context.source_to_reference['other'] = path
                with self.assertRaisesRegex(ValueError, 'transformação'):
                    prepare_model_inputs([InputBinding('T1c', 'other')], self.ref,
                                         self.spec, self.context)
                self.assertFalse((self.context.job_dir / 'prepared').exists())

    def test_valid_composite_registration_preserves_asymmetric_channel(self):
        other = SeriesDescriptor('other', '', 'subject', 'study', 'MR',
                                  geometry(self.image), source_format='nifti')
        self.context.series_index['other'] = other
        self.context.authorized_inputs['other'] = self.path
        composite = sitk.CompositeTransform(3)
        composite.AddTransform(sitk.TranslationTransform(3, (3, -2, 1)))
        composite.AddTransform(sitk.TranslationTransform(3, (-3, 2, -1)))
        path = self.root / 'valid_composite.tfm'
        sitk.WriteTransform(composite, str(path))
        self.context.source_to_reference['other'] = path
        prepared = prepare_model_inputs([InputBinding('T1c', 'other')], self.ref,
                                        self.spec, self.context)
        np.testing.assert_allclose(sitk.GetArrayFromImage(sitk.ReadImage(
            prepared.channel_paths[0])), self.array, atol=1e-5)

    def test_channels_are_ordered_and_duplicate_source_is_rejected(self):
        self.spec['channels'] = [{'role': 'T1c'}, {'role': 'FLAIR'}]
        with self.assertRaisesRegex(ValueError, 'repetida'):
            prepare_model_inputs([InputBinding('FLAIR', 'ref'), InputBinding('T1c', 'ref')],
                                 self.ref, self.spec, self.context)

    def test_ordered_multichannel_preparation_preserves_distinct_intensities(self):
        path = self.root / 'flair.nii.gz'
        sitk.WriteImage(self.image + 7, str(path))
        flair = SeriesDescriptor('flair', '', 'subject', 'study', 'MR',
                                  geometry(self.image), source_format='nifti')
        self.context.series_index['flair'] = flair
        self.context.authorized_inputs['flair'] = path
        transform_path = self.root / 'aligned.tfm'
        sitk.WriteTransform(sitk.Transform(3, sitk.sitkIdentity), str(transform_path))
        self.context.source_to_reference['flair'] = transform_path
        self.spec['channels'] = [{'role': 'T1c'}, {'role': 'FLAIR'}]
        prepared = prepare_model_inputs([InputBinding('FLAIR', 'flair'), InputBinding('T1c', 'ref')],
                                        self.ref, self.spec, self.context)
        self.assertEqual(prepared.channel_roles, ['T1c', 'FLAIR'])
        np.testing.assert_allclose(sitk.GetArrayFromImage(sitk.ReadImage(prepared.channel_paths[0])),
                                   self.array, atol=1e-5)
        np.testing.assert_allclose(sitk.GetArrayFromImage(sitk.ReadImage(prepared.channel_paths[1])),
                                   self.array + 7, atol=1e-5)

    def test_cropped_working_mask_returns_to_physical_location_without_array_padding_guess(self):
        prepared = prepare_model_inputs(self.context.bindings, self.ref, self.spec, self.context)
        # Cropped non-central block includes the small focus next to x boundary.
        crop = self.image[8:11, 1:4, 0:3]
        path = self.root / 'crop.nii.gz'
        sitk.WriteImage(sitk.Cast(crop, sitk.sitkUInt8), str(path))
        result = ModelResult('MRI_GBM', 'completed', [MaskArtifact(
            'MRI_GBM', 'tumor', str(path), geometry(crop), 'working')])
        output = sitk.ReadImage(restore_masks(result, prepared, self.ref)[0].path)
        expected = np.zeros_like(self.array)
        expected[1, 2, 9] = 1
        np.testing.assert_array_equal(sitk.GetArrayFromImage(output), expected)
        point = output.TransformIndexToPhysicalPoint((9, 2, 1))
        np.testing.assert_allclose(point, self.image.TransformIndexToPhysicalPoint((9, 2, 1)),
                                   atol=1e-5, rtol=0)

    def test_finer_working_grid_restores_binary_labels_without_fractional_values(self):
        prepared = prepare_model_inputs(self.context.bindings, self.ref, self.spec, self.context)
        fine = sitk.Resample(self.image, [21, 17, 13], sitk.Transform(3, sitk.sitkIdentity),
                            sitk.sitkNearestNeighbor, self.image.GetOrigin(), (.35, .65, 1.05),
                            self.image.GetDirection(), 0, sitk.sitkUInt8)
        path = self.root / 'fine.nii.gz'
        sitk.WriteImage(fine, str(path))
        result = ModelResult('MRI_GBM', 'completed', [MaskArtifact(
            'MRI_GBM', 'tumor', str(path), geometry(fine), 'working')])
        output = sitk.ReadImage(restore_masks(result, prepared, self.ref)[0].path)
        np.testing.assert_array_equal(sitk.GetArrayFromImage(output), self.array)
        self.assertEqual(output.GetPixelID(), sitk.sitkUInt8)

    def test_unknown_ticket_cannot_be_used_as_a_path(self):
        with self.assertRaisesRegex(ValueError, 'autorizado'):
            prepare_model_inputs([InputBinding('T1c', str(self.path))], self.ref,
                                 self.spec, self.context)

    def test_probability_mask_is_rejected_without_silent_threshold(self):
        prepared = prepare_model_inputs(self.context.bindings, self.ref, self.spec, self.context)
        probability = self.image * .8
        path = self.root / 'prob.nii.gz'
        sitk.WriteImage(probability, str(path))
        result = ModelResult('MRI_GBM', 'completed', [MaskArtifact(
            'MRI_GBM', 'tumor', str(path), geometry(probability), 'working')])
        with self.assertRaisesRegex(ValueError, 'binária'):
            restore_masks(result, prepared, self.ref)

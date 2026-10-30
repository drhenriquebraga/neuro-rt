"""Synthetic geometry only: no clinical images, weights or inference."""
from pathlib import Path
import sys
import unittest

import numpy as np
import SimpleITK as sitk

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'RECON_3D/app'))
import radai_projection as N


class NidusConsensusCoreTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(getattr(N, 'consenso', None)), 'The consensus geometry API is not implemented')
        self.image = sitk.Image([21, 17, 13], sitk.sitkInt16)
        self.image.SetSpacing((.8, 1.3, 2.1))
        self.image.SetOrigin((-32., 41., -19.))
        a, b = np.deg2rad([23., 11.])
        rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1.]])
        rx = np.array([[1., 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
        self.image.SetDirection(tuple((rz @ rx).ravel()))
        self.incidences = [
            {'lao': 0., 'cra': 0., 'pontos': [(19, 21), (44, 21), (44, 43), (19, 43)]},
            {'lao': 63., 'cra': 17., 'pontos': [(22, 19), (43, 19), (43, 45), (22, 45)]}]

    def tubes(self):
        return [N.tubo(self.image, inc['pontos'], inc['lao'], inc['cra'], lado=64) for inc in self.incidences]

    def test_endpoints_match_existing_backprojections_bit_for_bit(self):
        consensus = N.consenso(self.image, self.incidences, lado=64)
        tubes = self.tubes()
        np.testing.assert_array_equal(consensus.mask(0), np.logical_or.reduce(tubes))
        np.testing.assert_array_equal(consensus.mask(100), np.logical_and.reduce(tubes))
        self.assertEqual(consensus.geometry['size'], list(self.image.GetSize()))
        self.assertEqual(consensus.geometry['direction'], list(self.image.GetDirection()))

    def test_temperature_is_nested_and_one_incidence_does_not_change(self):
        consensus = N.consenso(self.image, self.incidences, lado=64)
        before = consensus.mask(0)
        for temperature in (1, 13, 25, 50, 67, 99, 100):
            after = consensus.mask(temperature)
            self.assertFalse(np.any(after & ~before))
            before = after
        one = N.consenso(self.image, self.incidences[:1], lado=64)
        for temperature in (0, 50, 100):
            np.testing.assert_array_equal(one.mask(temperature), self.tubes()[0])

    def test_preview_has_the_same_oblique_physical_mask_as_the_original_grid(self):
        consensus = N.consenso(self.image, self.incidences, lado=64)
        eixos = N.eixos_lps(self.image)
        view = N.para_lps(consensus.mask(42), eixos)
        for axis in range(3):
            for index in (0, view.shape[axis] // 2, view.shape[axis] - 1):
                np.testing.assert_array_equal(consensus.plane(42, axis, index), N.corte(view, axis, index))

    def test_chunks_are_bounded_and_keep_original_grid_without_float_stacks(self):
        tiled = N.consenso(self.image, self.incidences, lado=64, chunk_voxels=256)
        normal = N.consenso(self.image, self.incidences, lado=64)
        np.testing.assert_array_equal(tiled.mask(47), normal.mask(47))
        self.assertLessEqual(tiled.max_chunk_voxels, 256)
        packed = tiled.packed(47)
        self.assertEqual(packed.shape, tuple(reversed(self.image.GetSize())))
        self.assertEqual(packed.bits.shape[-1], (self.image.GetSize()[0] + 7) // 8)

    def test_empty_silhouette_and_contradictory_incidence_are_not_discarded(self):
        empty = {'lao': 0., 'cra': 0., 'pontos': [(-100, -100), (-90, -100), (-90, -90)]}
        consensus = N.consenso(self.image, [self.incidences[0], empty], lado=64)
        self.assertTrue(consensus.mask(0).any())
        self.assertFalse(consensus.mask(100).any())
        self.assertFalse(N.consenso(self.image, [empty], lado=64).mask(50).any())

    def test_invalid_temperature_and_geometry_input_are_refused(self):
        consensus = N.consenso(self.image, self.incidences, lado=64)
        for value in (-1, 101, float('nan'), float('inf'), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                consensus.mask(value)
        with self.assertRaises(ValueError):
            N.consenso(self.image, [], lado=64)


if __name__ == '__main__':
    unittest.main()

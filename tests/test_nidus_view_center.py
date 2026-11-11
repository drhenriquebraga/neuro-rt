import unittest
import numpy as np
from neuro_rt.nidus_view_center import consensus_center


class Core:
    def __init__(self, mask):
        self.mask = mask
        self.calls = []

    def plane(self, temperature, axis, index):
        self.calls.append((temperature, axis, index))
        return self.mask[index].copy()


class Candidate:
    def __init__(self, mask):
        self.mask = mask

    def plane(self, axis, index):
        return self.mask[index].copy()


class CenterTests(unittest.TestCase):
    def test_exact_voxel_centroid_and_mpr_positions_without_mutating_mask(self):
        mask = np.zeros((9, 11, 13), dtype=bool)
        mask[2:5, 4:7, 8:11] = True
        before = mask.copy()
        core = Core(mask)
        result = consensus_center(core, mask.shape, 70)
        self.assertEqual(result['centro'], [3., 5., 9.])
        self.assertEqual(result['posicoes'], [3/8, 5/10, 9/12])
        self.assertEqual(result['voxels'], 27)
        np.testing.assert_array_equal(mask, before)
        self.assertEqual(core.calls, [(70, 0, index) for index in range(9)])

    def test_edited_suggestion_is_used_and_empty_is_explicit(self):
        empty = np.zeros((3, 4, 5), dtype=bool)
        edited = empty.copy(); edited[1, 2, 3] = True
        self.assertEqual(consensus_center(Core(empty), empty.shape, 100), {'vazio': True, 'voxels': 0})
        result = consensus_center(Core(empty), empty.shape, 100, Candidate(edited))
        self.assertEqual(result['centro'], [1., 2., 3.])

    def test_anisotropic_rotated_reference_and_disconnected_voxels(self):
        mask = np.zeros((9, 11, 13), dtype=bool)
        mask[2:5, 4:7, 8:11] = True
        core = Core(mask)
        core.eixos = ((2, 0, 1), (True, False, True))
        core.geometry = {'spacing': [.7, 1.5, 2.5], 'origin': [100., 200., 300.],
                         'direction': [0., -1., 0., 1., 0., 0., 0., 0., 1.]}
        result = consensus_center(core, mask.shape, 50)
        np.testing.assert_allclose(result['centro_lps_mm'], [95.5, 203.5, 312.5])
        disconnected = np.zeros((5, 5, 5), dtype=bool)
        disconnected[0, 0, 0] = True
        disconnected[4, 3:5, 4] = True
        result = consensus_center(Core(disconnected), disconnected.shape, 50)
        np.testing.assert_allclose(result['centro'], [8/3, 7/3, 8/3])
        self.assertTrue(all(0 <= position <= 1 for position in result['posicoes']))

    def test_invalid_temperature_or_shape_is_rejected(self):
        core = Core(np.zeros((3, 4, 5), dtype=bool))
        for temperature in (float('nan'), -1, 101):
            with self.assertRaises(ValueError):
                consensus_center(core, (3, 4, 5), temperature)
        with self.assertRaises(ValueError):
            consensus_center(core, (3, 4, 6), 50)

    def test_real_candidate_orientation_maps_back_to_original_physical_centroid(self):
        import SimpleITK as sitk
        import radai_projection as N
        from types import SimpleNamespace
        from neuro_rt.nidus_geometry import NidusCandidate
        image = sitk.Image([13, 11, 9], sitk.sitkInt16)
        image.SetSpacing((.7, 1.5, 2.5))
        image.SetOrigin((100., 200., 300.))
        angle = np.deg2rad(21.)
        image.SetDirection((0., -np.cos(angle), np.sin(angle),
                            1., 0., 0., 0., np.sin(angle), np.cos(angle)))
        mask = np.zeros((9, 11, 13), dtype=bool)
        mask[1:4, 3:8, 5:10] = True
        core = SimpleNamespace(geometry={key: list(value) for key, value in (
            ('size', image.GetSize()), ('spacing', image.GetSpacing()),
            ('origin', image.GetOrigin()), ('direction', image.GetDirection()))},
            eixos=N.eixos_lps(image), temperature=float,
            packed=lambda temperature, progress=None: N.compactar(mask))
        candidate = NidusCandidate(core, 60)
        result = consensus_center(core, candidate.view_shape, 60, candidate)
        expected = image.TransformContinuousIndexToPhysicalPoint(tuple(np.mean(np.argwhere(mask), axis=0)[::-1]))
        np.testing.assert_allclose(result['centro_lps_mm'], expected)
        np.testing.assert_array_equal(candidate.mask(), mask)


if __name__ == '__main__':
    unittest.main()

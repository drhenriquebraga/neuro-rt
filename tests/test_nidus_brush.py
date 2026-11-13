"""Physical brush/eraser and LPS mesh tests on synthetic anisotropic oblique data."""
from pathlib import Path
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import SimpleITK as sitk

recon_app = Path(os.environ.get('RADAI_RECON_APP', str(Path(__file__).resolve().parents[2] /
                                                   'radai-suite-release-v816/_montagem/componentes/RECON_3D/app')))
sys.path[:0] = [str(recon_app), str(recon_app.parents[1] / '3D_PRINTED_BOLUS/app')]
import radai_projection as N
from neuro_rt.nidus_geometry import NidusCandidate


def candidate_for(image, mask=None):
    mask = np.zeros(tuple(reversed(image.GetSize())), bool) if mask is None else mask
    core = SimpleNamespace(geometry={key: list(value) for key, value in (
        ('size', image.GetSize()), ('spacing', image.GetSpacing()), ('origin', image.GetOrigin()),
        ('direction', image.GetDirection()))}, eixos=N.eixos_lps(image), temperature=float,
        packed=lambda temperature, progress=None: N.compactar(mask))
    return NidusCandidate(core, 50)


def oblique_image():
    image = sitk.Image([23, 17, 11], sitk.sitkUInt8)
    image.SetSpacing((.7, 1.2, 2.))
    image.SetOrigin((20., -30., 40.))
    angle = np.deg2rad(17)
    rotation = np.array([[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1.]])
    permutation = np.array([[0, 0, -1.], [-1., 0, 0], [0, 1., 0]])
    image.SetDirection(tuple((rotation @ permutation).ravel()))
    return image


class PhysicalBrush(unittest.TestCase):
    def test_seventy_two_high_entropy_grayscale_pngs_and_eight_decoded_views_fit_budget(self):
        import radai_recon3d as R
        image = np.random.default_rng(123).integers(0, 256, size=(1024, 1024), dtype=np.uint8)
        png = R.para_png(image, 127.5, 255.)
        self.assertEqual(png[25], 0, 'Native projections must stay grayscale PNG, not RGB/RGBA payloads')
        self.assertLess(len(png), 1.1 * 1024 * 1024)
        compressed_plus_eight_decoded = 72 * len(png) + 8 * 1024 * 1024 * 4
        self.assertLess(compressed_plus_eight_decoded, 128 * 1024 * 1024)

    def test_disk_mm_matches_native_lps_distances_in_all_mpr_planes(self):
        image = oblique_image()
        zyx = np.indices(tuple(reversed(image.GetSize()))).reshape(3, -1).T
        xyz = zyx[:, ::-1]
        direction = np.array(image.GetDirection()).reshape(3, 3)
        lps = (xyz * image.GetSpacing()) @ direction.T + image.GetOrigin()
        for axis in range(3):
            with self.subTest(axis=axis):
                candidate = candidate_for(image)
                index = candidate.view_shape[axis] // 2
                shape = candidate.plane(axis, index).shape
                row, col = shape[0] // 2, shape[1] // 2
                view = ([index, row, col] if axis == 0 else
                        [candidate.view_shape[0] - 1 - row, index, col] if axis == 1 else
                        [candidate.view_shape[0] - 1 - row, col, index])
                native = [0, 0, 0]
                for v_axis, n_axis in enumerate(candidate.eixos[0]):
                    native[n_axis] = candidate.view_shape[v_axis] - 1 - view[v_axis] if candidate.eixos[1][v_axis] else view[v_axis]
                center_lps = image.TransformIndexToPhysicalPoint(tuple(reversed(native)))
                radius = 2.1
                same_plane = zyx[:, candidate.eixos[0][axis]] == native[candidate.eixos[0][axis]]
                expected = (same_plane & (np.linalg.norm(lps - center_lps, axis=1) <= radius + 1e-7)).reshape(candidate.packed.shape)
                before = candidate.packed.bits.copy()
                changed = candidate.brush(axis, index, [[(col + .5) / shape[1], (row + .5) / shape[0]]], 'add', radius)
                np.testing.assert_array_equal(candidate.mask(), expected)
                self.assertEqual(changed, int(expected.sum()))
                self.assertEqual(candidate.geometry['direction'], list(image.GetDirection()))
                self.assertTrue(candidate.undo())
                np.testing.assert_array_equal(candidate.packed.bits, before)

    def test_continuous_capsule_stroke_eraser_and_one_step_undo(self):
        image = sitk.Image([31, 21, 7], sitk.sitkUInt8)
        image.SetSpacing((.5, 1., 2.))
        candidate = candidate_for(image)
        points = [[(5.5) / 31, (10.5) / 21], [(25.5) / 31, (10.5) / 21]]
        candidate.brush(0, 3, points, 'add', .6)
        mask = candidate.mask()
        self.assertTrue(mask[3, 10, 5:26].all(), 'Sparse pointer events must leave a continuous stroke')
        self.assertFalse(mask[:3].any())
        self.assertFalse(mask[4:].any())
        self.assertEqual(len(candidate.history), 1)
        candidate.brush(0, 3, [[15.5 / 31, 10.5 / 21]], 'remove', 1.1)
        self.assertFalse(candidate.mask()[3, 10, 15])
        self.assertTrue(candidate.undo())
        np.testing.assert_array_equal(candidate.mask(), mask)
        self.assertEqual(candidate.metadata()['approval_status'], 'UNAPPROVED')

    def test_invalid_or_noop_brush_does_not_mutate_revision(self):
        candidate = candidate_for(oblique_image())
        for points, radius, operation in (([[.5, .5]], float('nan'), 'add'),
                                          ([[1.1, .5]], 1, 'add'), ([[.5, .5]], 1, 'replace'),
                                          ([], 1, 'add'), ([[.5, .5]] * 257, 1, 'add')):
            with self.assertRaises(ValueError):
                candidate.brush(0, 2, points, operation, radius)
        self.assertEqual(candidate.revision, 1)
        self.assertEqual(candidate.brush(0, 2, [[.5, .5]], 'remove', 1), 0)
        self.assertEqual(candidate.revision, 1)
        self.assertFalse(candidate.metadata()['undo_available'])

    def test_mesh_vertices_preserve_native_voxel_boundary_in_lps(self):
        from neuro_rt.nidus_consensus_mesh import candidate_mesh
        image = oblique_image()
        mask = np.zeros(tuple(reversed(image.GetSize())), bool)
        mask[3:7, 5:12, 7:15] = True
        candidate = candidate_for(image, mask)
        before = candidate.packed.bits.copy()
        mesh = candidate_mesh(candidate)
        vertices = mesh['vertices']
        native_xyz = ((vertices - image.GetOrigin()) @ np.array(image.GetDirection()).reshape(3, 3)) / image.GetSpacing()
        np.testing.assert_allclose(native_xyz.min(axis=0), [6.5, 4.5, 2.5], atol=1e-5)
        np.testing.assert_allclose(native_xyz.max(axis=0), [14.5, 11.5, 6.5], atol=1e-5)
        self.assertGreater(len(mesh['faces']), 0)
        self.assertGreater(len(mesh['stl']), 84)
        np.testing.assert_array_equal(candidate.packed.bits, before)
        self.assertEqual(candidate.revision, 1)
        self.assertEqual(mesh['coordinate_system'], 'LPS_mm')

    def test_mesh_resource_refusal_keeps_editable_mask(self):
        from neuro_rt.nidus_consensus_mesh import candidate_mesh
        image = sitk.Image([20, 20, 20], sitk.sitkUInt8)
        mask = np.ones((20, 20, 20), bool)
        candidate = candidate_for(image, mask)
        with patch('neuro_rt.nidus_consensus_mesh.MAX_MESH_VOXELS', 10):
            with self.assertRaises(ValueError):
                candidate_mesh(candidate)
        np.testing.assert_array_equal(candidate.mask(), mask)


if __name__ == '__main__':
    unittest.main()

import unittest
import numpy as np
from neuro_rt.build_views import center_slices


class ViewCentersTests(unittest.TestCase):
    def test_disconnected_foci_open_on_segmented_slices(self):
        mask = np.zeros((16, 16, 16), dtype=bool)
        mask[1:3, 1:3, 1:3] = True
        mask[12:15, 12:15, 12:15] = True
        centroid = np.round(np.argwhere(mask).mean(0)).astype(int)
        self.assertFalse(mask.take(centroid[0], axis=0).any())
        for axis, index in enumerate(center_slices(mask)):
            self.assertTrue(mask.take(index, axis=axis).any())

    def test_empty_mask_still_opens_inside_each_plane(self):
        mask = np.zeros((4, 8, 12), dtype=bool)
        for count, index in zip(mask.shape, center_slices(mask)):
            self.assertGreaterEqual(index, 0)
            self.assertLess(index, count)


if __name__ == '__main__':
    unittest.main()

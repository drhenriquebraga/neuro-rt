import tempfile
import unittest
import importlib.util
from pathlib import Path
import numpy as np
import SimpleITK as sitk
from neuro_rt.adapters.attention_unet import AttentionUNetAdapter
from neuro_rt.adapters._scientific import ScientificPrediction, binary_masks
from neuro_rt.geometry_pipeline import verify_reference_geometry
from scientific_adapter_fixtures import context_for
from test_pipeline import TEMP_ROOT


class AttentionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.ctx = context_for(Path(self.tmp.name), 'glioma_attention_unet3d')

    def test_roles_and_identifiable_values_preserve_published_order(self):
        self.ctx.bindings.reverse()
        prepared = AttentionUNetAdapter().prepare(self.ctx)
        self.assertEqual(prepared.channel_roles, ['FLAIR', 'T1', 'T1c', 'T2'])
        values = [sitk.GetArrayFromImage(sitk.ReadImage(p)).max() for p in prepared.channel_paths]
        self.assertEqual(values, sorted(values))

    def test_independent_overlapping_regions_and_disconnected_foci_roundtrip(self):
        import nibabel as nib
        adapter = AttentionUNetAdapter()
        prepared = adapter.prepare(self.ctx)
        image = nib.load(prepared.channel_paths[0])
        tc = np.zeros(image.shape, np.uint8)
        tc[1:4, 2:5, 3:6] = 1
        tc[-4:-1, -5:-2, -6:-3] = 1
        wt = tc.copy(); wt[0:6, 0:7, 0:8] = 1
        et = np.zeros_like(tc); et[2, 3, 4] = 1
        masks = binary_masks([tc, wt, et], image.affine, adapter.classes, self.ctx)
        result = adapter.normalize_result(ScientificPrediction(prepared, masks, [], {}, {}), self.ctx)
        self.assertEqual([m.class_id for m in result.masks], list(adapter.classes))
        for mask, expected in zip(result.masks, [tc, wt, et]):
            actual = nib.load(mask.path).get_fdata()
            np.testing.assert_array_equal(actual, expected)
            self.assertTrue(verify_reference_geometry(mask.path, self.ctx.reference).valid)

    def test_missing_duplicate_and_wrong_declared_channel_order_fail(self):
        adapter = AttentionUNetAdapter()
        self.ctx.model_spec['channels'].reverse()
        with self.assertRaisesRegex(ValueError, 'Ordem'): adapter.prepare(self.ctx)
        self.ctx.model_spec['channels'].reverse()
        self.ctx.bindings.pop()
        with self.assertRaises(ValueError): adapter.prepare(self.ctx)

    def test_all_zero_regions_are_empty_without_rois(self):
        import nibabel as nib
        adapter = AttentionUNetAdapter(); prepared = adapter.prepare(self.ctx)
        im = nib.load(prepared.channel_paths[0]); zero = np.zeros(im.shape, np.uint8)
        masks = binary_masks([zero]*3, im.affine, adapter.classes, self.ctx)
        result = adapter.normalize_result(ScientificPrediction(prepared, masks, [], {}, {}), self.ctx)
        self.assertEqual(result.status, 'empty'); self.assertEqual(result.masks, [])

    @unittest.skipUnless(importlib.util.find_spec('monai'), 'MONAI no runtime cientifico privado')
    def test_published_sliding_windows_include_far_edge_and_overlaps(self):
        import torch
        torch.set_num_threads(2)
        data=torch.full((1,4,129,5,7),-10.)
        data[0,0,0,1,1]=10; data[0,0,-1,3,5]=10
        data[0,1]=data[0,0]; data[0,2,-1,3,5]=10
        actual=AttentionUNetAdapter.infer_regions(lambda x:x[:,:3],data)
        np.testing.assert_array_equal(actual,(data[0,:3].numpy()>=0))

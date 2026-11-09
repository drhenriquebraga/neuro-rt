import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from neuro_rt.adapters.raidionics_postop import RaidionicsPostopAdapter
from neuro_rt.adapters._scientific import ScientificPrediction, binary_masks
from scientific_adapter_fixtures import context_for
from test_pipeline import TEMP_ROOT


class RaidionicsMultisequenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=TEMP_ROOT); self.addCleanup(self.tmp.cleanup)
        self.ctx=context_for(Path(self.tmp.name),'MRI_GBM_Postop_FV_3p')

    def test_shuffled_bindings_use_real_pipeline_order(self):
        self.ctx.bindings.reverse()
        self.assertEqual(RaidionicsPostopAdapter().prepare(self.ctx).channel_roles,['T1c','T1','FLAIR'])

    def test_distinct_series_require_explicit_registration_even_matching_headers(self):
        self.ctx.source_to_reference.clear()
        with self.assertRaisesRegex(ValueError,'registro'):RaidionicsPostopAdapter().prepare(self.ctx)

    def test_missing_or_duplicated_bindings_fail(self):
        self.ctx.bindings.pop()
        with self.assertRaises(ValueError):RaidionicsPostopAdapter().prepare(self.ctx)
        self.ctx.bindings.append(self.ctx.bindings[0])
        with self.assertRaises(ValueError):RaidionicsPostopAdapter().prepare(self.ctx)

    def test_present_uncertain_manual_binding_is_not_treated_as_missing(self):
        self.ctx.bindings[1]=replace(self.ctx.bindings[1],certainty='uncertain')
        self.assertEqual(len(RaidionicsPostopAdapter().prepare(self.ctx).channel_paths),3)

    def test_different_acquisition_moment_is_rejected(self):
        self.ctx.series_index['T1']=replace(self.ctx.series_index['T1'],study_key='preop_other_moment')
        with self.assertRaisesRegex(ValueError,'mesmo sujeito, estudo'):
            RaidionicsPostopAdapter().prepare(self.ctx)

    def test_residual_tumor_keeps_two_disconnected_foci_on_original_grid(self):
        import nibabel as nib
        import numpy as np
        from neuro_rt.geometry_pipeline import verify_reference_geometry
        adapter=RaidionicsPostopAdapter(); prepared=adapter.prepare(self.ctx)
        im=nib.load(prepared.channel_paths[0]); data=np.zeros(im.shape,np.uint8)
        data[1:4,2:5,3:6]=1;data[-4:-1,-5:-2,-6:-3]=1
        masks=binary_masks([data],im.affine,['tumor'],self.ctx)
        result=adapter.normalize_result(ScientificPrediction(prepared,masks,[],{},{}),self.ctx)
        self.assertEqual(len(result.masks),1)
        np.testing.assert_array_equal(nib.load(result.masks[0].path).get_fdata(),data)
        self.assertTrue(verify_reference_geometry(result.masks[0].path,self.ctx.reference).valid)

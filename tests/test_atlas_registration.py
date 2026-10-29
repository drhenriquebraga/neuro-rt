import tempfile
import unittest
import importlib.util
from pathlib import Path
import numpy as np
import SimpleITK as sitk
from neuro_rt.adapters.cerebra_ants import CerebraANTsAdapter
from neuro_rt.adapters._scientific import ScientificPrediction, label_masks, asset_spec, binary_masks
from neuro_rt.geometry_pipeline import verify_reference_geometry
from scientific_adapter_fixtures import context_for
from test_pipeline import TEMP_ROOT


class AtlasAdapterTests(unittest.TestCase):
    def test_nonfinite_or_singular_physical_transform_is_rejected(self):
        for value in (np.nan, 0.):
            affine=np.eye(4); affine[0,0]=value
            with self.assertRaisesRegex(ValueError,'Transformação'):
                binary_masks([np.zeros((3,3,3))],affine,['any'],None)

    @unittest.skipUnless(importlib.util.find_spec('ants'), 'ANTs no runtime cientifico privado')
    def test_ants_known_transform_label_direction_and_inverse(self):
        import ants
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            data=np.zeros((24,24,24),np.float32)
            data[8:11,5:8,3:6]=1; data[15:18,12:15,9:12]=52
            image=ants.from_numpy(data)
            tx=ants.create_ants_transform(transform_type='Euler3DTransform',translation=(2,0,0))
            path=str(Path(tmp)/'shift.mat'); ants.write_transform(tx,path)
            shifted=ants.apply_transforms(fixed=image,moving=image,transformlist=[path],interpolator='genericLabel')
            expected=np.zeros_like(data); expected[:-2]=data[2:]
            np.testing.assert_array_equal(shifted.numpy(),expected)
            restored=ants.apply_transforms(fixed=image,moving=shifted,transformlist=[path],
                                           whichtoinvert=[True],interpolator='genericLabel')
            np.testing.assert_array_equal(restored.numpy(),data)

    def test_exact102_label_table_and_asymmetric_laterality_roundtrip(self):
        import nibabel as nib
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            ctx = context_for(Path(tmp), 'anatomy_cerebra_ants')
            adapter = CerebraANTsAdapter(); prepared=adapter.prepare(ctx)
            im=nib.load(prepared.channel_paths[0]); labels=np.zeros(im.shape,np.int16)
            labels[1:3, 5:8, 4:7]=1; labels[-5:-2, 9:12, 7:9]=52
            table=asset_spec(ctx.model_spec['id'])['contract']['classes']
            self.assertEqual({c['value'] for c in table}, set(range(1,103)))
            masks=label_masks(labels,im.affine,ctx)
            result=adapter.normalize_result(ScientificPrediction(prepared,masks,[],{},{}),ctx)
            self.assertEqual(len(result.masks),2)
            for m in result.masks:self.assertTrue(verify_reference_geometry(m.path,ctx.reference).valid)

    def test_known_physical_translation_restores_without_header_replacement(self):
        import nibabel as nib
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            ctx=context_for(Path(tmp),'anatomy_cerebra_ants'); adapter=CerebraANTsAdapter()
            prepared=adapter.prepare(ctx); im=nib.load(prepared.channel_paths[0])
            labels=np.zeros(im.shape,np.int16); labels[3:6,4:7,5:8]=1
            shifted_affine=im.affine.copy(); shifted_affine[:3,3] += im.affine[:3,0]*2
            masks=label_masks(labels,shifted_affine,ctx)
            result=adapter.normalize_result(ScientificPrediction(prepared,masks,[],{},{}),ctx)
            expected=np.zeros_like(labels); expected[5:8,4:7,5:8]=1
            np.testing.assert_array_equal(nib.load(result.masks[0].path).get_fdata(),expected)

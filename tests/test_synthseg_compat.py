"""Compatibility against audited DIPY 1.12 sources on the unchanged host base."""
import ast
import hashlib
import importlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
REFERENCE=ROOT/'models/anatomy_synthseg/reference'
REVISION='407e9319cbfe3d05304682d317363ecd09a83fdc'


def reference_module(name,file):
    spec=importlib.util.spec_from_file_location(name,file)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SynthSegCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.compat=importlib.import_module('neuro_rt.compat_synthseg')
        self.utils=importlib.import_module('neuro_rt.compat_synthseg_utils')

    def reference_utils(self):
        file=REFERENCE/'utils.py'
        if not file.is_file(): self.skipTest('Pinned optional model sources are absent.')
        self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),
            '8fe8d9e3f609a92801cb50aaaba25e9cfea6308a06c276986e9c7e108737878f')
        return reference_module('_synthseg_reference_utils',file)

    def test_geometry_matches_pinned_transform_and_nearest_recovery(self):
        reference=self.reference_utils()
        a=np.deg2rad(21.)
        rotation=np.array([[np.cos(a),-np.sin(a),0],[np.sin(a),np.cos(a),0],[0,0,1.]])
        affines=[np.eye(4),np.diag([.8,1.4,2.1,1.]),np.eye(4)]
        affines[-1][:3,:3]=rotation@np.diag([-1.2,.7,1.8]);affines[-1][:3,3]=[31.,-42.,13.]
        data=np.random.default_rng(71).normal(size=(13,17,11)).astype(np.float32)
        for affine in affines:
            for final in ((16,20,14),(8,10,9)):
                with self.subTest(affine=affine.tolist(),final=final):
                    expected,params=reference.transform_img(data,affine,target_voxsize=(1.,1.,1.),final_size=final,order=3)
                    actual,current=self.utils.transform_img(data,affine,target_voxsize=(1.,1.,1.),final_size=final,order=3)
                    np.testing.assert_array_equal(actual,expected)
                    self.assertEqual(set(current),set(params))
                    for key in params: np.testing.assert_array_equal(current[key],params[key])
                    labels=(np.indices(final).sum(axis=0)%4).astype(np.int32)
                    recovered=self.utils.recover_img(labels,current,order=0)
                    np.testing.assert_array_equal(recovered,reference.recover_img(labels,params,order=0))
                    self.assertEqual(recovered.shape,data.shape)
                    self.assertTrue(set(np.unique(recovered))<={0,1,2,3})

    def test_identity_recovery_preserves_native_grid_interior_and_original_affine(self):
        labels=np.zeros((13,17,11),np.int32);labels[2:5,4:8,3:6]=41
        affine=np.eye(4);affine[:3,3]=[31.,-42.,13.]
        transformed,params=self.utils.transform_img(labels,affine,target_voxsize=(1,1,1),final_size=(20,22,18),order=0)
        recovered=self.utils.recover_img(transformed,params,order=0)
        np.testing.assert_array_equal(recovered,labels)
        np.testing.assert_array_equal(params['ori_affine'],affine)

    def test_topology_keeps_holes_when_requested_and_removes_islands(self):
        binary=np.zeros((11,13,9),bool);binary[2:8,2:9,2:7]=True
        binary[4:6,4:6,3:5]=False;binary[0,0,0]=True
        result=self.compat.remove_holes_and_islands(binary,remove_holes=False)
        self.assertEqual(result[0,0,0],0)
        self.assertFalse(result[4:6,4:6,3:5].any())
        self.assertEqual(result.sum(),binary.sum()-1)
        for value in (False,True):
            np.testing.assert_array_equal(self.compat.remove_holes_and_islands(
                np.full((3,4,5),value),remove_holes=False),np.full((3,4,5),value))

    def test_topology_matches_official_same_revision_source(self):
        file=ROOT/'.research/synthseg-dipy-407e9319-segment-utils.py'
        if not file.is_file(): self.skipTest('Optional audit source is absent.')
        reference=reference_module('_synthseg_reference_segment',file)
        binary=np.zeros((11,13,9),bool);binary[2:8,2:9,2:7]=True
        binary[4:6,4:6,3:5]=False;binary[0,0,0]=True
        for holes,islands,slice_wise in ((False,True,False),(True,True,False),(True,False,True)):
            kwargs=dict(remove_holes=holes,remove_islands=islands,slice_wise=slice_wise)
            np.testing.assert_array_equal(self.compat.remove_holes_and_islands(binary,**kwargs),
                reference.remove_holes_and_islands(binary,**kwargs))

    def test_architecture_and_prediction_method_are_ast_identical_to_reference(self):
        file=REFERENCE/'synthseg.py'
        if not file.is_file(): self.skipTest('Pinned optional model sources are absent.')
        self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),
            'aef78a8a9a47975c22cfcdf87dcd0ed7dc982e6c4b5fb450991286c32ec1091d')
        original=ast.parse(file.read_text(encoding='utf-8'))
        current=ast.parse(Path(self.compat.__file__).read_text(encoding='utf-8'))
        classes=lambda tree:{node.name:node for node in tree.body if isinstance(node,ast.ClassDef)}
        before,after=classes(original),classes(current)
        for name in ('Conv3dELU','Block','Model'):
            self.assertEqual(ast.dump(before[name]),ast.dump(after[name]))
        methods=lambda cls:{node.name:node for node in cls.body if isinstance(node,ast.FunctionDef)}
        for name,node in methods(before['SynthSeg']).items():
            if name!='fetch_default_weights': self.assertEqual(ast.dump(node),ast.dump(methods(after['SynthSeg'])[name]))
        self.assertIn(REVISION,self.compat.COMPAT_REVISION)

    def test_local_import_does_not_replace_dipy_helpers_and_default_download_is_disabled(self):
        import dipy.nn.utils as original_utils
        import dipy.segment.utils as original_segment
        transform,recover,topology=original_utils.transform_img,original_utils.recover_img,original_segment.remove_holes_and_islands
        importlib.reload(self.compat)
        self.assertIs(original_utils.transform_img,transform)
        self.assertIs(original_utils.recover_img,recover)
        self.assertIs(original_segment.remove_holes_and_islands,topology)
        instance=object.__new__(self.compat.SynthSeg)
        with patch('socket.socket',side_effect=AssertionError('Network forbidden')):
            with self.assertRaisesRegex(RuntimeError,'peso|weight'): instance.fetch_default_weights()

    def test_strict_official_checkpoint_and_small_forward_work_with_host_torch(self):
        import torch
        weights=ROOT/'models/anatomy_synthseg/synthseg_model_weights.pth'
        if not weights.is_file(): self.skipTest('Optional 53 MB official checkpoint is absent.')
        self.assertEqual(hashlib.sha256(weights.read_bytes()).hexdigest(),
            '3023c046e3996796b1e87badeb337cc7edd2da4c79794a0214afc76b63c701fe')
        class OfflineSynthSeg(self.compat.SynthSeg):
            def fetch_default_weights(self): self.load_model_weights(weights)
        instance=OfflineSynthSeg(verbose=False,use_cuda=False)
        model=instance.model
        self.assertEqual(str(instance.device),'cpu')
        self.assertEqual(len(instance.labels_segmentation),33)
        self.assertEqual(len(instance.label_dict),33)
        self.assertEqual(len(model.state_dict()),83)
        self.assertEqual(sum(p.numel() for p in model.parameters()),13240641)
        threads=torch.get_num_threads();torch.set_num_threads(2)
        try:
            with torch.inference_mode(): output=model(torch.zeros((1,1,32,32,32)))
        finally: torch.set_num_threads(threads)
        self.assertEqual(tuple(output.shape),(1,33,32,32,32))
        self.assertTrue(torch.isfinite(output).all().item())
        torch.testing.assert_close(output.sum(1),torch.ones((1,32,32,32)))


if __name__=='__main__': unittest.main()

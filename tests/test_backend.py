"""Teste com backend/ONNX reais e rede pequena sintética, sem pesos clínicos."""
import tempfile
import unittest
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import onnx
import SimpleITK as sitk
from onnx import TensorProto, helper, numpy_helper

from neuro_rt.worker import run_job
from neuro_rt import catalog
from test_pipeline import TEMP_ROOT


def synthetic_model(root, model_id='MRI_GBM', label='Tumor', brain_crop=False):
    folder = Path(root) / model_id
    (folder / 'fold0').mkdir(parents=True)
    x = helper.make_tensor_value_info('input', TensorProto.FLOAT, [1, 8, 8, 8, 1])
    y = helper.make_tensor_value_info('output', TensorProto.FLOAT, [1, 8, 8, 8, 2])
    one = numpy_helper.from_array(np.array(1., dtype=np.float32), 'one')
    graph = helper.make_graph([helper.make_node('Sub', ['one', 'input'], ['background']),
                               helper.make_node('Concat', ['background', 'input'], ['output'], axis=4)],
                              'synthetic', [x], [y], [one])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 13)])
    model.ir_version = 8
    onnx.save(model, folder / 'fold0' / 'model.onnx')
    text = f'''[Default]
imaging_modality=MRI
[PreProcessing]
intensity_clipping_range=0,100
intensity_final_range=0,1
output_spacing=1,1,1
new_axial_size=8,8,8
background_cropping={'brain_mask' if brain_crop else ''}
normalization_method=default
number_inputs=1
[Training]
nb_classes=2
classes=Background,{label}
deep_supervision=True
optimal_thresholds=0.5,0.5
'''
    (folder / 'pre_processing.ini').write_text(text)
    receipt = {'model_id':model_id,'release':'1.2.0','files':{
        name:hashlib.sha256((folder/name).read_bytes()).hexdigest()
        for name in ('pre_processing.ini','fold0/model.onnx')}}
    (folder/'provenance.json').write_text(json.dumps(receipt))
    catalog.MODEL_LOCK[model_id] = receipt
    return folder


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.lock_patch = patch.dict(catalog.MODEL_LOCK, {}, clear=True)
        self.lock_patch.start()

    def tearDown(self):
        self.lock_patch.stop()

    def test_actual_backend_produces_binary_native_geometry(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            models = root / 'models'
            synthetic_model(models)
            array = np.linspace(0., .15, 512, dtype=np.float32).reshape((8, 8, 8))
            array[1:4, 3:6, 5:7] += .8
            image = sitk.GetImageFromArray(array)
            image.SetOrigin((45., -30., 12.))
            path = root / 'synthetic.nii.gz'
            sitk.WriteImage(image, str(path))
            job = root / 'job'
            job.mkdir()
            result = run_job({'model': 'MRI_GBM', 'input_path': str(path), 'explicit_request': True}, job, models)
            self.assertEqual(result['approval_status'], 'UNAPPROVED')
            mask = sitk.GetArrayFromImage(sitk.ReadImage(str(job / 'masks' / 'Tumor.nii.gz')))
            np.testing.assert_array_equal(mask > 0, array > .5)
            self.assertEqual(result['masks'][0]['voxels'], 18)

    def test_actual_backend_preserves_oblique_native_grid(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            synthetic_model(root / 'models')
            array = np.linspace(0.,.15,512,dtype=np.float32).reshape((8,8,8))
            array[1:4,3:6,5:7] += .8
            image = sitk.GetImageFromArray(array)
            angle = np.deg2rad(20.)
            image.SetDirection((np.cos(angle),-np.sin(angle),0.,np.sin(angle),np.cos(angle),0.,0.,0.,1.))
            image.SetSpacing((.8,1.2,2.))
            image.SetOrigin((45.,-30.,12.))
            path = root / 'oblique.nii.gz'
            sitk.WriteImage(image,str(path))
            job = root / 'job'; job.mkdir()
            result = run_job({'model':'MRI_GBM','input_path':str(path),'explicit_request':True},job,root/'models')
            self.assertEqual(result['geometry']['size_xyz'],[8,8,8])
            self.assertTrue(result['masks'][0]['voxels'] > 0)

    def test_missing_receipt_and_modified_weight_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            folder = synthetic_model(tmp)
            model = catalog.get_model('MRI_GBM')
            receipt = (folder/'provenance.json').read_text()
            (folder/'provenance.json').unlink()
            with self.assertRaises(ValueError):
                catalog.validate_model_folder(folder,model)
            (folder/'provenance.json').write_text(receipt)
            with (folder/'fold0/model.onnx').open('ab') as handle:
                handle.write(b'changed')
            with self.assertRaises(ValueError):
                catalog.validate_model_folder(folder,model)


if __name__ == '__main__':
    unittest.main()

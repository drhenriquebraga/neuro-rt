"""Adapter integration with the existing real ONNX/backend synthetic fixture."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import onnx
import SimpleITK as sitk
from onnx import helper, numpy_helper

from neuro_rt import catalog
from neuro_rt.adapters.base import ModelRunContext, RunCancelled
from neuro_rt.adapters.raidionics import RaidionicsAdapter
from neuro_rt.imaging import geometry
from neuro_rt.study_types import InputBinding, SeriesDescriptor
from neuro_rt.worker import run_job
from test_backend import synthetic_model
from test_pipeline import TEMP_ROOT


class RaidionicsAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        lock = patch.dict(catalog.MODEL_LOCK, {}, clear=True)
        lock.start()
        self.addCleanup(lock.stop)
        self.folder = synthetic_model(self.root / 'models', brain_crop=True)
        brain_folder = synthetic_model(self.root / 'models', 'MRI_Brain', 'Brain')
        # A synthetic connected brain enclosing both foci. The published backend
        # keeps the largest *brain* component during skull stripping.
        brain_path = brain_folder / 'fold0/model.onnx'
        brain_model = onnx.load(brain_path)
        foreground = np.zeros((1, 8, 8, 8, 2), np.float32)
        foreground[..., 1] = 1
        del brain_model.graph.node[:]
        del brain_model.graph.initializer[:]
        brain_model.graph.node.append(helper.make_node('Constant', [], ['output'],
                                        value=numpy_helper.from_array(foreground)))
        onnx.save(brain_model, brain_path)
        import hashlib
        import json
        receipt = json.loads((brain_folder / 'provenance.json').read_text())
        receipt['files']['fold0/model.onnx'] = hashlib.sha256(brain_path.read_bytes()).hexdigest()
        (brain_folder / 'provenance.json').write_text(json.dumps(receipt))
        catalog.MODEL_LOCK['MRI_Brain'] = receipt
        array = np.linspace(0, .15, 512, dtype=np.float32).reshape(8, 8, 8)
        array[1:3, 2:4, 5:7] += .8
        array[5:7, 5:7, 1:3] += .8
        self.image = sitk.GetImageFromArray(array)
        self.image.SetOrigin((31, -47, 19))
        path = self.root / 'input.nii.gz'
        sitk.WriteImage(self.image, str(path))
        ref = SeriesDescriptor('ref', '', 's', 'study', 'MR', geometry(self.image),
                               source_format='nifti')
        spec = {'id': 'MRI_GBM', 'adapter_id': 'raidionics',
                'channels': [{'role': 'T1c'}],
                'classes': [{'class_id': 'tumor', 'label': 'Tumor'}]}
        self.context = ModelRunContext(spec, [InputBinding('T1c', 'ref')], ref,
                                      {'ref': ref}, {'ref': path},
                                      self.root / 'job', self.root / 'models', 'cpu')

    def test_real_backend_matches_legacy_keeps_all_foci_and_auxiliary_private(self):
        legacy_job = self.root / 'legacy'
        legacy_job.mkdir()
        run_job({'model': 'MRI_GBM', 'input_path': str(self.context.authorized_inputs['ref']),
                 'device': 'cpu', 'explicit_request': True}, legacy_job, self.context.models_dir)
        adapter = RaidionicsAdapter()
        prepared = adapter.prepare(self.context)
        raw = adapter.predict(prepared, self.context)
        result = adapter.normalize_result(raw, self.context)
        self.assertEqual(result.status, 'completed')
        self.assertEqual([(m.model_id, m.class_id) for m in result.masks], [('MRI_GBM', 'tumor')])
        actual = sitk.GetArrayFromImage(sitk.ReadImage(result.masks[0].path))
        expected = sitk.GetArrayFromImage(sitk.ReadImage(str(legacy_job / 'masks/Tumor.nii.gz')))
        np.testing.assert_array_equal(actual, expected)
        self.assertTrue(actual[1:3, 2:4, 5:7].any())
        self.assertTrue(actual[5:7, 5:7, 1:3].any())
        self.assertTrue(result.versions['engine'])
        self.assertIn('weights', result.hashes)
        self.assertFalse(list(self.context.job_dir.rglob('*.dcm')))

    def test_cancellation_does_not_start_inference(self):
        self.context.cancel_requested = lambda: True
        with self.assertRaises(RunCancelled):
            RaidionicsAdapter().prepare(self.context)
        self.assertFalse(self.context.job_dir.exists())

    def test_cancellation_after_preparation_does_not_start_backend(self):
        adapter = RaidionicsAdapter()
        prepared = adapter.prepare(self.context)
        self.context.cancel_requested = lambda: True
        with self.assertRaises(RunCancelled):
            adapter.predict(prepared, self.context)
        self.assertFalse((self.context.job_dir / 'raidionics').exists())

    def test_corrupted_weight_fails_without_export(self):
        with (self.folder / 'fold0/model.onnx').open('ab') as handle:
            handle.write(b'corrupt')
        adapter = RaidionicsAdapter()
        prepared = adapter.prepare(self.context)
        with self.assertRaisesRegex(ValueError, 'alterado|corrompido'):
            adapter.predict(prepared, self.context)

    def test_unresolved_device_is_not_silently_accepted(self):
        self.context.device = 'auto'
        with self.assertRaisesRegex(ValueError, 'dispositivo'):
            RaidionicsAdapter().prepare(self.context)

    def test_strict_cuda_fails_without_silent_cpu_fallback_when_provider_absent(self):
        import onnxruntime as ort
        if 'CUDAExecutionProvider' in ort.get_available_providers():
            self.skipTest('Este ambiente possui CUDA; a validação de GPU exige teste próprio.')
        self.context.device = 'cuda'
        adapter = RaidionicsAdapter()
        with self.assertRaisesRegex(ValueError, 'CUDA indisponível'):
            adapter.predict(adapter.prepare(self.context), self.context)

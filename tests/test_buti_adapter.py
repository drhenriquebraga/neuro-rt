"""Buti host boundary with synthetic CT and a controlled inference script."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import SimpleITK as sitk

from neuro_rt.adapters.base import ModelRunContext
from neuro_rt.imaging import geometry
from neuro_rt.study_types import InputBinding, SeriesDescriptor


CLASSES = ['Brain', 'Brainstem', 'Cerebellum', 'Chiasm', 'OpticNerve_L',
           'OpticNerve_R', 'Ventricles_connected', 'Midline']
TRAINER = 'nnUNetTrainer__nnUNetPlans__3d_fullres'


class ButiAdapterTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parents[1] / 'runtime/test-temp'
        temp_root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=temp_root)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.host = self.root / 'host'; self.host.mkdir()
        self.models = self.host / 'modelos/cranio_buti'
        self.trainer = self.models / TRAINER
        (self.trainer / 'fold_all').mkdir(parents=True)
        files = {'dataset.json': json.dumps({'labels': {'background': 0, **{
            name: i for i, name in enumerate(CLASSES, 1)}}, 'channel_names': {'0': 'CT'}}).encode(),
            'plans.json': b'{}', 'dataset_fingerprint.json': b'{}',
            'fold_all/checkpoint_final.pth': b'synthetic checkpoint'}
        sizes, hashes = [], {}
        for rel, data in files.items():
            path = self.trainer / rel; path.write_bytes(data)
            name = TRAINER + '/' + rel
            sizes.append((name, len(data))); hashes[name] = hashlib.sha256(data).hexdigest()
        metadata = {'arquivos': sizes, 'sha256': hashes, 'revisao': 'synthetic-revision'}
        (self.host / 'radai_models.py').write_text(
            'from pathlib import Path\nMODELOS=' + repr({'cranio_buti': metadata}) + '\n'
            'def pasta_do_modelo(ident): return Path(__file__).parent / "modelos" / ident\n')
        script = '''
import sys
def _principal():
    import SimpleITK as s
    import numpy as n
    from pathlib import Path
    image=s.ReadImage(sys.argv[2]); data=n.zeros(tuple(reversed(image.GetSize())), n.uint8)
    for i in range(1,9): data[1,1,i]=i
    data[4,4,9]=1
    output=s.GetImageFromArray(data); output.CopyInformation(image)
    s.WriteImage(output, str(Path(sys.argv[3]) / 'case.nii.gz'))
'''
        (self.host / 'radai_cranio_engine.py').write_text(
            'ROTULOS_CONFERIDOS=' + repr(dict(enumerate(CLASSES, 1))) + '\n'
            'def conferir_rotulos(table):\n'
            '    if table != ROTULOS_CONFERIDOS: raise ValueError("classes divergentes")\n'
            '_SCRIPT=' + repr(script) + '\n')
        image = sitk.GetImageFromArray(np.zeros((7, 9, 11), np.float32))
        image.SetSpacing((.7, 1.3, 2.1)); image.SetOrigin((31., -47., 19.))
        a = np.deg2rad(23)
        image.SetDirection((np.cos(a), -np.sin(a), 0., np.sin(a), np.cos(a), 0., 0., 0., 1.))
        path = self.root / 'ct.nii.gz'; sitk.WriteImage(image, str(path))
        ref = SeriesDescriptor('ct', '', 'synthetic', 'study', 'CT', geometry(image), source_format='nifti')
        spec = {'id': 'cranio_buti', 'adapter_id': 'buti_host', 'revision': 'synthetic-revision',
                'channels': [{'role': 'CT'}], 'reference_role': 'CT',
                'classes': [{'class_id': c, 'label': c} for c in CLASSES]}
        self.context = ModelRunContext(spec, [InputBinding('CT', 'ct')], ref, {'ct': ref},
            {'ct': path}, self.root / 'job', self.root / 'neuro_models', 'cpu')
        self.context.host_app = self.host
        self.context.host_python = Path(sys.executable)
        self.torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False), __version__='stub')

    def adapter(self):
        from neuro_rt.adapters.buti_ct import ButiCTAdapter
        return ButiCTAdapter()

    def run_adapter(self):
        adapter = self.adapter()
        prepared = adapter.prepare(self.context)
        with patch.dict(sys.modules, {'torch': self.torch}):
            raw = adapter.predict(prepared, self.context)
        return adapter.normalize_result(raw, self.context)

    def test_keeps_all_eight_classes_and_disconnected_foci_on_original_oblique_grid(self):
        result = self.run_adapter()
        self.assertEqual([m.class_id for m in result.masks], CLASSES)
        self.assertEqual(result.status, 'completed')
        for mask in result.masks:
            image = sitk.ReadImage(mask.path)
            np.testing.assert_allclose(image.GetDirection(), self.context.reference.geometry['direction_lps'], atol=1e-5)
            self.assertEqual(image.GetSize(), (11, 9, 7))
            self.assertEqual(mask.space, 'reference')
        brain = sitk.GetArrayFromImage(sitk.ReadImage(result.masks[0].path))
        self.assertEqual(int(brain.sum()), 2)
        self.assertEqual(brain[1, 1, 1], 1)
        self.assertEqual(brain[4, 4, 9], 1)
        self.assertFalse(self.context.models_dir.exists())

    def test_rejects_gpu_without_cuda_instead_of_falling_back(self):
        self.context.device = 'cuda'
        with self.assertRaisesRegex(RuntimeError, 'CUDA'):
            self.run_adapter()

    def test_rejects_mr_and_unresolved_device(self):
        self.context.reference = replace(self.context.reference, modality='MR')
        with self.assertRaisesRegex(ValueError, 'TC|CT'):
            self.adapter().prepare(self.context)
        self.context.reference = replace(self.context.reference, modality='CT')
        self.context.device = 'auto'
        with self.assertRaisesRegex(ValueError, 'cpu|cuda'):
            self.adapter().prepare(self.context)

    def test_rejects_an_input_outside_authorized_inventory(self):
        self.context.authorized_inputs = {}
        with self.assertRaisesRegex(ValueError, 'autorizado'):
            self.adapter().prepare(self.context)

    def test_different_ct_requires_explicit_transform(self):
        ref = self.context.reference
        other = replace(ref, ticket='other')
        self.context.series_index['other'] = other
        self.context.authorized_inputs['other'] = self.context.authorized_inputs['ct']
        self.context.bindings = [InputBinding('CT', 'other')]
        with self.assertRaisesRegex(ValueError, 'registro'):
            self.adapter().prepare(self.context)
        transform = self.root / 'source_to_reference.tfm'
        sitk.WriteTransform(sitk.Transform(3, sitk.sitkIdentity), str(transform))
        self.context.source_to_reference['other'] = transform
        self.assertEqual(len(self.run_adapter().masks), 8)

    def test_rejects_altered_weight_bytes(self):
        (self.trainer / 'fold_all/checkpoint_final.pth').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'Artefato|corrompido'):
            self.run_adapter()

    def test_rejects_foreign_classes_even_if_host_table_changes(self):
        engine = self.host / 'radai_cranio_engine.py'
        engine.write_text(engine.read_text().replace("'OpticNerve_R'", "'Unexpected'"))
        with self.assertRaisesRegex(ValueError, 'rótulos|classes'):
            self.run_adapter()

    def test_rejects_invalid_output_labels(self):
        engine = self.host / 'radai_cranio_engine.py'
        engine.write_text(engine.read_text().replace('data[4,4,9]=1', 'data[4,4,9]=9'))
        with self.assertRaisesRegex(ValueError, 'rótulos'):
            self.run_adapter()

    def test_rejects_a_shifted_output_header_instead_of_relabeling_geometry(self):
        engine = self.host / 'radai_cranio_engine.py'
        engine.write_text(engine.read_text().replace('output.CopyInformation(image)',
            'output.CopyInformation(image); output.SetOrigin((999., 0., 0.))'))
        with self.assertRaisesRegex(ValueError, 'Geometria'):
            self.run_adapter()

    def test_cancelled_before_inference_has_no_result(self):
        from neuro_rt.adapters.base import RunCancelled
        self.context.cancel_requested = lambda: True
        with self.assertRaises(RunCancelled):
            self.run_adapter()

    def test_capability_is_disabled_for_unknown_python_and_missing_weights(self):
        from integration.buti_host import capabilities
        self.assertFalse(capabilities(self.host, '?')['cranio_buti']['available'])
        python = self.root / 'python/python.exe'; python.parent.mkdir(); python.write_bytes(b'exe')
        for name in ('nnunetv2', 'torch', 'numpy', 'SimpleITK'):
            (python.parent / 'Lib/site-packages' / name).mkdir(parents=True)
        capability = capabilities(self.host, python)['cranio_buti']
        self.assertTrue(capability['available'], capability['reason'])
        (self.trainer / 'fold_all/checkpoint_final.pth').unlink()
        self.assertFalse(capabilities(self.host, python)['cranio_buti']['available'])

    def test_capability_does_not_import_scientific_packages(self):
        from integration.buti_host import capabilities
        python = self.root / 'python/python.exe'; python.parent.mkdir(); python.write_bytes(b'exe')
        for name in ('nnunetv2', 'torch', 'numpy', 'SimpleITK'):
            (python.parent / 'Lib/site-packages' / name).mkdir(parents=True)
        import builtins
        real_import = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name.split('.')[0] in ('torch', 'nnunetv2', 'SimpleITK', 'numpy', 'nibabel'):
                raise AssertionError('Scientific import in capability provider: ' + name)
            return real_import(name, *args, **kwargs)
        with patch('builtins.__import__', guarded):
            self.assertTrue(capabilities(self.host, python)['cranio_buti']['available'])


if __name__ == '__main__': unittest.main()

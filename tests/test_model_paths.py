"""Revision selection uses synthetic folders, never clinical data or real weights."""
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from neuro_rt import model_paths
from neuro_rt import catalog
from neuro_rt.model_registry import verify_artifacts


class ModelPathTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / '.research' / 'test_plugin_tmp'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='model paths ', dir=root)
        self.addCleanup(self.temp.cleanup)
        self.models = Path(self.temp.name) / 'models'
        self.models.mkdir()

    def test_exact_revision_wins_and_missing_revision_never_selects_latest(self):
        model = self.models / 'fixture'
        (model / '1').mkdir(parents=True)
        (model / '9').mkdir()
        self.assertEqual(model_paths.resolve_model_folder(self.models, 'fixture', revision='1'), model / '1')
        self.assertEqual(model_paths.resolve_model_folder(self.models, 'fixture', revision='2'), model / '2')
        self.assertEqual(model_paths.resolve_model_folder(self.models, 'fixture', revision='2', allow_legacy=True), model)

    def test_legacy_flat_folder_requires_explicit_development_flag(self):
        flat = self.models / 'fixture'
        flat.mkdir()
        self.assertEqual(model_paths.resolve_model_folder(self.models, 'fixture', revision='1'), flat / '1')
        self.assertEqual(model_paths.resolve_model_folder(self.models, 'fixture', revision='1', allow_legacy=True), flat)
        for model_id, revision in (('../outside', '1'), ('fixture', '../outside'), ('fixture', 'latest/../../x')):
            with self.assertRaises(ValueError):
                model_paths.resolve_model_folder(self.models, model_id, revision=revision)

    def test_installed_artifacts_verify_exact_revision_without_flat_fallback(self):
        from types import SimpleNamespace
        folder = self.models / 'fixture' / '1'
        folder.mkdir(parents=True)
        data = b'synthetic weight'
        (folder / 'model.onnx').write_bytes(data)
        spec = {'id': 'fixture', 'revision': '1', 'catalog_state': 'distributed',
                'artifacts': [{'path': 'model.onnx', 'sha256': hashlib.sha256(data).hexdigest()}]}
        installed = SimpleNamespace(models_dir=self.models, plugin_root=self.models.parent)
        self.assertEqual(verify_artifacts(spec, installed)['status'], 'ready')
        (self.models / 'fixture' / 'model.onnx').write_bytes(data)
        (folder / 'model.onnx').unlink()
        self.assertEqual(verify_artifacts(spec, installed)['status'], 'missing')

    def _weight_fixture(self, model_id, classes, crop='none'):
        folder = self.models / model_id / catalog.RELEASE
        (folder / 'fold0').mkdir(parents=True)
        ini = ('[Default]\nimaging_modality=MRI\n[PreProcessing]\nnumber_inputs=1\n'
               f'background_cropping={crop}\n[Training]\nclasses=Background,{classes}\nnb_classes=2\n').encode()
        files = {'pre_processing.ini': ini, 'fold0/model.onnx': b'synthetic ' + model_id.encode()}
        hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
        for name, data in files.items():
            (folder / name).write_bytes(data)
        (folder / 'provenance.json').write_text(json.dumps({'model_id': model_id, 'release': catalog.RELEASE, 'files': hashes}))
        return folder, {'files': hashes}

    def test_shared_preflight_and_status_resolve_tumor_and_brain_same_revision(self):
        tumor, tumor_lock = self._weight_fixture('MRI_GBM', 'Tumor', crop='brain_mask')
        brain, brain_lock = self._weight_fixture(catalog.BRAIN['id'], 'Brain')
        with patch.dict(catalog.MODEL_LOCK, {'MRI_GBM': tumor_lock, catalog.BRAIN['id']: brain_lock}):
            self.assertEqual(model_paths.preflight_model_folders(self.models, catalog.get_model('MRI_GBM')), (tumor, brain))
            state = next(m for m in model_paths.shared_model_status(self.models) if m['id'] == 'MRI_GBM')
            self.assertTrue(state['ready'], state['reason'])
            (brain / 'fold0' / 'model.onnx').write_bytes(b'bad')
            with self.assertRaises(ValueError):
                model_paths.preflight_model_folders(self.models, catalog.get_model('MRI_GBM'))

    def test_worker_uses_versioned_tumor_and_auxiliary_with_synthetic_backend(self):
        import configparser
        import SimpleITK as sitk
        from neuro_rt.worker import run_job
        tumor, tumor_lock = self._weight_fixture('MRI_GBM', 'Tumor', crop='brain_mask')
        brain, brain_lock = self._weight_fixture(catalog.BRAIN['id'], 'Brain')
        source = self.models.parent / 'synthetic.nii.gz'
        image = sitk.Image([7, 8, 9], sitk.sitkFloat32)
        image.SetSpacing((0.9, 1.2, 2.1))
        sitk.WriteImage(image, str(source))
        job = self.models.parent / 'synthetic job'
        job.mkdir()
        selected = []
        def fake_engine(*, config_filename):
            cfg = configparser.ConfigParser()
            cfg.read(config_filename)
            folder = Path(cfg['System']['model_folder'])
            selected.append(folder)
            mask = sitk.Image(image.GetSize(), sitk.sitkUInt8)
            mask.CopyInformation(image)
            mask[2, 3, 4] = 1
            label = 'Brain' if folder == brain else 'Tumor'
            sitk.WriteImage(mask, str(Path(cfg['System']['output_folder']) / ('labels_' + label + '.nii.gz')))
        fit = types.ModuleType('raidionicsseg.fit')
        fit.run_model = fake_engine
        with patch.dict(catalog.MODEL_LOCK, {'MRI_GBM': tumor_lock, catalog.BRAIN['id']: brain_lock}), \
                patch.dict('sys.modules', {'raidionicsseg': types.ModuleType('raidionicsseg'),
                                          'raidionicsseg.fit': fit, 'onnxruntime': types.ModuleType('onnxruntime')}), \
                patch('neuro_rt.worker.importlib.metadata.version', return_value='synthetic-fixture'):
            result = run_job({'model': 'MRI_GBM', 'input_path': str(source), 'series_uid': '',
                              'device': 'cpu', 'explicit_request': True, 'export_rtstruct': False},
                             job, self.models, allow_legacy_models=False)
        self.assertEqual(selected, [brain, tumor])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['brain_model_id'], catalog.BRAIN['id'])


if __name__ == '__main__':
    unittest.main()

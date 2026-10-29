import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from test_pipeline import TEMP_ROOT


class ModelCatalogTests(unittest.TestCase):
    def test_catalog_preserves_existing_models_and_five_candidates(self):
        from neuro_rt.model_registry import load_catalog, get_model_spec
        models = load_catalog()
        self.assertEqual(sum(m['catalog_state'] == 'candidate' and m['addition'] for m in models), 5)
        self.assertEqual(get_model_spec('MRI_GBM')['classes'], [{'class_id': 'tumor', 'label': 'Tumor'}])
        self.assertEqual(get_model_spec('glioma_attention_unet3d')['channels'],
                         [{'role': r} for r in ('FLAIR', 'T1', 'T1c', 'T2')])
        spec = get_model_spec('MRI_GBM')
        spec['classes'].clear()
        self.assertTrue(get_model_spec('MRI_GBM')['classes'])

    def test_duplicate_id_and_unknown_license_are_rejected(self):
        from neuro_rt.model_registry import load_catalog
        source = Path(__file__).resolve().parents[1] / 'catalog/models.json'
        data = json.loads(source.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            path = Path(tmp) / 'catalog.json'
            broken = copy.deepcopy(data)
            broken['models'].append(copy.deepcopy(broken['models'][0]))
            path.write_text(json.dumps(broken), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_catalog(path)
            broken = copy.deepcopy(data)
            broken['models'][0]['license']['weights'] = 'LicenseRef-noncommercial'
            path.write_text(json.dumps(broken), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_catalog(path)

    def test_artifacts_require_complete_files_and_detect_corruption(self):
        from neuro_rt.model_registry import verify_artifacts
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            folder = root / 'fixture'
            folder.mkdir()
            content = b'example-weight-bytes'
            (folder / 'model.onnx').write_bytes(content)
            spec = {'id': 'fixture', 'catalog_state': 'distributed', 'revision': '1',
                    'artifacts': [{'path': 'model.onnx', 'sha256': hashlib.sha256(content).hexdigest(),
                                   'size': len(content)}]}
            self.assertEqual(verify_artifacts(spec, root)['status'], 'ready')
            (folder / 'model.onnx').write_bytes(b'corrupt')
            self.assertEqual(verify_artifacts(spec, root)['status'], 'corrupt')
            (folder / 'model.onnx').unlink()
            self.assertEqual(verify_artifacts(spec, root)['status'], 'missing')

    def test_html_and_unlocked_assets_cannot_be_ready(self):
        from neuro_rt.model_registry import verify_artifacts, get_model_spec
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            folder = root / 'fixture'
            folder.mkdir()
            content = b'<!doctype html><html>not a checkpoint</html>'
            (folder / 'model.onnx').write_bytes(content)
            spec = {'id': 'fixture', 'catalog_state': 'distributed', 'revision': '1',
                    'artifacts': [{'path': 'model.onnx', 'sha256': hashlib.sha256(content).hexdigest()}]}
            self.assertEqual(verify_artifacts(spec, root)['status'], 'corrupt')
            self.assertEqual(verify_artifacts(get_model_spec('metastasis_qtim'), root)['status'], 'candidate')

    def test_artifact_path_cannot_leave_model_directory(self):
        from neuro_rt.model_registry import verify_artifacts
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            spec = {'id': 'fixture', 'catalog_state': 'distributed', 'revision': '1',
                    'artifacts': [{'path': '../secret', 'sha256': '0' * 64}]}
            self.assertEqual(verify_artifacts(spec, Path(tmp))['status'], 'corrupt')

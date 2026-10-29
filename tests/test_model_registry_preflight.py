"""Preflight/runtime inventory regressions with tiny local files, no weights."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from neuro_rt.model_registry import get_model_spec, verify_artifacts
from test_pipeline import TEMP_ROOT


class ModelRegistryPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.spec = self._model('primary', b'small-primary')
        self.dependency = self._model('auxiliary', b'small-auxiliary')
        self.spec['dependencies'] = [self.dependency]

    def _model(self, model_id, data):
        folder = self.root / model_id / '1'
        folder.mkdir(parents=True)
        (folder / 'weight.bin').write_bytes(data)
        return {'id': model_id, 'revision': '1', 'catalog_state': 'verified',
                'artifacts': [{'path': 'weight.bin', 'sha256': hashlib.sha256(data).hexdigest(),
                               'size': len(data)}]}

    def test_required_dependency_is_verified_before_model_can_be_ready(self):
        self.assertEqual(verify_artifacts(self.spec, self.root)['status'], 'ready')
        weight = self.root / 'auxiliary/1/weight.bin'
        weight.unlink()
        report = verify_artifacts(self.spec, self.root)
        self.assertEqual(report['status'], 'missing')
        self.assertIn('auxiliary/1/weight.bin', report['missing_files'])
        weight.write_bytes(b'corrupted-auxiliary')
        self.assertEqual(verify_artifacts(self.spec, self.root)['status'], 'corrupt')

    def test_runtime_provenance_is_required_and_identity_checked(self):
        self.dependency['provenance'] = {'path': 'provenance.json', 'release': '1'}
        report = verify_artifacts(self.spec, self.root)
        self.assertEqual(report['status'], 'missing')
        receipt = self.root / 'auxiliary/1/provenance.json'
        receipt.write_text(json.dumps({'model_id': 'different', 'release': '1', 'files': {}}))
        self.assertEqual(verify_artifacts(self.spec, self.root)['status'], 'corrupt')
        receipt.write_text(json.dumps({'model_id': 'auxiliary', 'release': '1', 'files': {
            'weight.bin': self.dependency['artifacts'][0]['sha256']}}))
        self.assertEqual(verify_artifacts(self.spec, self.root)['status'], 'ready')

    def test_expected_html_license_is_hashed_but_html_weights_stay_forbidden(self):
        content = b'<!doctype html><html>Original licensing evidence</html>'
        folder = self.root / 'primary/1'
        (folder / 'LICENSE.atlas-DOI.html').write_bytes(content)
        evidence = {'path': 'LICENSE.atlas-DOI.html', 'format': 'html',
                    'purpose': 'licensing_evidence', 'size': len(content),
                    'sha256': hashlib.sha256(content).hexdigest()}
        self.spec['artifacts'].append(evidence)
        self.assertEqual(verify_artifacts(self.spec, self.root)['status'], 'ready')
        (folder / 'LICENSE.atlas-DOI.html').write_bytes(content + b'corruption')
        self.assertEqual(verify_artifacts(self.spec, self.root)['status'], 'corrupt')
        (folder / 'LICENSE.atlas-DOI.html').unlink()
        self.assertEqual(verify_artifacts(self.spec, self.root)['status'], 'missing')
        (folder / 'LICENSE.atlas-DOI.html').write_bytes(content)
        for mutation in ({'purpose': 'weights'}, {'format': 'text'}, {'size': None}):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(self.spec)
                changed['artifacts'][-1].update(mutation)
                self.assertEqual(verify_artifacts(changed, self.root)['status'], 'corrupt')
        # Marking a checkpoint as licensing evidence cannot bypass the guard.
        (folder / 'weight.bin').write_bytes(content)
        changed = copy.deepcopy(self.spec)
        changed['artifacts'][0] = {**evidence, 'path': 'weight.bin'}
        self.assertEqual(verify_artifacts(changed, self.root)['status'], 'corrupt')

    def test_dependency_revision_never_falls_back_to_another_revision(self):
        self.dependency['revision'] = '2'
        self.assertEqual(verify_artifacts(self.spec, self.root)['status'], 'missing')

    def test_dependency_cycles_are_rejected(self):
        self.dependency['dependencies'] = [copy.deepcopy(self.spec)]
        self.assertEqual(verify_artifacts(self.spec, self.root)['status'], 'corrupt')

    def test_catalog_declares_the_actual_brain_dependencies_and_all_scientific_files(self):
        expected_brain = ('MRI_GBM', 'MRI_LGGlioma', 'MRI_Metastasis',
                          'MRI_GBM_Postop_FV_1p', 'MRI_GBM_Postop_FV_3p')
        for model_id in expected_brain:
            with self.subTest(model_id=model_id):
                spec = get_model_spec(model_id)
                self.assertEqual([d['id'] for d in spec.get('dependencies', [])], ['MRI_Brain'])
                dependency = spec['dependencies'][0]
                self.assertEqual(dependency['revision'], '1.2.0')
                self.assertEqual(dependency['provenance'],
                                  {'path': 'provenance.json', 'release': '1.2.0'})
                self.assertIn('fold0/model.onnx', [a['path'] for a in dependency['artifacts']])
        self.assertEqual(get_model_spec('MRI_Meningioma').get('dependencies', []), [])
        root = Path(__file__).resolve().parents[1]
        manifest_path = root / 'catalog/model_assets_v1_manifest.json'
        if not manifest_path.is_file():
            manifest_path = root / 'scripts/model_assets_v1_manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        for model_id, asset in manifest['models'].items():
            with self.subTest(model_id=model_id):
                declared = {entry['path']: entry for entry in get_model_spec(model_id)['artifacts']}
                self.assertEqual(set(declared), set(asset['files']))
                for path, entry in asset['files'].items():
                    self.assertEqual(declared[path]['sha256'], entry['sha256'])
                    self.assertEqual(declared[path]['size'], entry['size'])

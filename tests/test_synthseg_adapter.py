import tempfile
import unittest
import hashlib
from pathlib import Path
from unittest.mock import patch
import numpy as np
from neuro_rt.adapters.synthseg import SynthSegAdapter
from neuro_rt.adapters._scientific import ScientificPrediction, label_masks, asset_spec, verified_assets
from neuro_rt.geometry_pipeline import verify_reference_geometry
from scientific_adapter_fixtures import context_for
from test_pipeline import TEMP_ROOT


class SynthSegAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=TEMP_ROOT); self.addCleanup(self.tmp.cleanup)
        self.ctx = context_for(Path(self.tmp.name), 'anatomy_synthseg')

    def test_exact_32_labels_left_right_and_all_foci_survive_restoration(self):
        import nibabel as nib
        adapter = SynthSegAdapter(); prepared = adapter.prepare(self.ctx)
        im = nib.load(prepared.channel_paths[0]); labels = np.zeros(im.shape, np.int16)
        labels[2:4, 3:6, 4:7] = 2; labels[-4:-2, 3:6, 4:7] = 41
        labels[10, 20, 10] = 2
        table = asset_spec('anatomy_synthseg')['contract']['classes']
        self.assertEqual(len(table), 32)
        masks = label_masks(labels, im.affine, self.ctx)
        result = adapter.normalize_result(ScientificPrediction(prepared, masks, [], {}, {}), self.ctx)
        by_id = {m.class_id:m for m in result.masks}
        for label, key in [(2, 'left_cerebral_white_matter'), (41, 'right_cerebral_white_matter')]:
            np.testing.assert_array_equal(nib.load(by_id[key].path).get_fdata(), labels == label)
            self.assertTrue(verify_reference_geometry(by_id[key].path, self.ctx.reference).valid)

    def test_strict_cuda_not_silently_cpu(self):
        self.ctx.device='cuda'
        with self.assertRaisesRegex(ValueError, 'CPU'): SynthSegAdapter().prepare(self.ctx)

    def test_unknown_label_and_nan_fail_before_publication(self):
        for value in (999, np.nan):
            with self.assertRaisesRegex(ValueError, 'labels'):
                label_masks(np.full((4, 4, 4), value), np.eye(4), self.ctx)

    def test_revision_exact_assets_and_explicit_legacy_mode(self):
        data=b'pinned-weight'
        spec={'files':{'weight.pth':{'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}}}
        base=self.ctx.models_dir/self.ctx.model_spec['id']; base.mkdir(parents=True)
        (base/'weight.pth').write_bytes(data)
        self.ctx.allow_legacy_models=False
        with patch('neuro_rt.adapters._scientific.asset_spec',return_value=spec):
            with self.assertRaises(FileNotFoundError):verified_assets(self.ctx)
            self.ctx.allow_legacy_models=True
            self.assertEqual(verified_assets(self.ctx)[0],base.resolve())
            version=base/self.ctx.model_spec['revision']; version.mkdir()
            (version/'weight.pth').write_bytes(data)
            (base/'weight.pth').write_bytes(b'corrupt flat ignored')
            self.ctx.allow_legacy_models=False
            self.assertEqual(verified_assets(self.ctx)[0],version.resolve())
            (version/'weight.pth').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'corrompido'):verified_assets(self.ctx)

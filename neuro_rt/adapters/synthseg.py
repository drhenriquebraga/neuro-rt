"""Pinned SynthSeg CPU compatibility on the unchanged host DIPY/PyTorch base."""
from ._scientific import ScientificAdapter, ScientificPrediction, verified_assets, label_masks


class SynthSegAdapter(ScientificAdapter):
    roles = ('T1',)
    cpu_only = True

    def predict(self, prepared, context):
        import dipy
        import nibabel as nib
        import numpy as np
        import torch
        from ..compat_synthseg import SynthSeg, COMPAT_REVISION
        context.checkpoint('running', 0.)
        folder, hashes = verified_assets(context)
        if context.device != 'cpu':
            raise ValueError('SynthSeg DIPY habilitado somente em CPU.')
        # Override the downloader at instance-class scope, leaving upstream globals
        # untouched. Constructor still establishes the exact original label/TTA tables.
        class OfflineSynthSeg(SynthSeg):
            def fetch_default_weights(self):
                self.load_model_weights(str(folder / 'synthseg_model_weights.pth'))
        model = OfflineSynthSeg(verbose=False, use_cuda=False)
        image = nib.load(prepared.channel_paths[0])
        with torch.inference_mode():
            labels, table, _ = model.predict(image.get_fdata(dtype=np.float32), image.affine)
        artifacts = label_masks(labels, image.affine, context)
        context.checkpoint('running', 1.)
        return ScientificPrediction(prepared, artifacts, [{
            'operation': 'DIPY_SynthSeg_predict', 'spacing_mm': [1, 1, 1],
            'crop_size': [192, 192, 192], 'flip_tta': True,
            'recovery_interpolation_order': 0, 'upstream_topological_cleanup': True}],
            {'engine': 'dipy-synthseg-compat/' + COMPAT_REVISION,
             'dipy_base': dipy.__version__, 'torch': torch.__version__}, hashes)

"""Pinned Motaz Attention U-Net; complete published 128-cube sliding windows."""
from ._scientific import ScientificAdapter, ScientificPrediction, verified_assets, binary_masks


class AttentionUNetAdapter(ScientificAdapter):
    roles = ('FLAIR', 'T1', 'T1c', 'T2')
    classes = ('tumor_core', 'whole_tumor', 'enhancing_tumor')

    @staticmethod
    def infer_regions(model, tensor):
        import torch
        from monai.inferers import sliding_window_inference
        with torch.inference_mode():
            output = sliding_window_inference(tensor, (128, 128, 128), 1, model, overlap=.5)
            if not torch.isfinite(output).all():
                raise ValueError('Predição Attention U-Net não finita.')
            return (torch.sigmoid(output[0]) >= .5).cpu().numpy()

    def predict(self, prepared, context):
        import monai
        import nibabel as nib
        import numpy as np
        import torch
        from monai.networks.nets import AttentionUnet
        from monai.transforms import (Compose, LoadImaged, EnsureChannelFirstd, EnsureTyped,
                                      Orientationd, Spacingd, NormalizeIntensityd)
        context.checkpoint('running', 0.)
        folder, hashes = verified_assets(context)
        if context.device == 'cuda' and not torch.cuda.is_available():
            raise ValueError('CUDA indisponível; não haverá fallback silencioso.')
        images = [nib.load(p) for p in prepared.channel_paths]
        volume = np.stack([im.get_fdata(dtype=np.float32) for im in images], axis=-1)
        stacked = context.job_dir / 'ordered_channels.nii.gz'
        nib.save(nib.Nifti1Image(volume, images[0].affine), stacked)
        transform = Compose([LoadImaged('image'), EnsureChannelFirstd('image'),
                             EnsureTyped('image'), Orientationd('image', axcodes='RAS'),
                             Spacingd('image', pixdim=(1., 1., 1.), mode='bilinear'),
                             NormalizeIntensityd('image', nonzero=True, channel_wise=True)])
        data = transform({'image': str(stacked)})['image']
        model = AttentionUnet(spatial_dims=3, in_channels=4, out_channels=3,
                              channels=(32, 64, 128, 256, 512), strides=(2, 2, 2, 2), dropout=.1)
        state = torch.load(folder / 'best_model.pth', map_location='cpu', weights_only=True)
        model.load_state_dict(state['model_state_dict'], strict=True)
        model.eval().to(context.device)
        masks = self.infer_regions(model, data.unsqueeze(0).to(context.device))
        affine = np.asarray(data.affine)
        artifacts = binary_masks(masks, affine, self.classes, context)
        context.checkpoint('running', 1.)
        return ScientificPrediction(prepared, artifacts, [{
            'operation': 'monai_RAS_spacing_1mm_nonzero_channel_normalization',
            'roi_size': [128, 128, 128], 'overlap': .5, 'activation': 'sigmoid',
            'threshold': .5, 'output_order': list(self.classes)}],
            {'engine': 'monai/' + monai.__version__, 'torch': torch.__version__}, hashes)

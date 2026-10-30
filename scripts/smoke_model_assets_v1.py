"""Opt-in synthetic weight/architecture smoke; does not segment an exam.

Use the private runtime documented in MODEL_ASSETS_V1.md. Small tensor forward
passes prove checkpoint compatibility, not whole-volume accuracy or geometry.
"""
import argparse
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'runtime/model_assets_v1_smoke.json')
    args = parser.parse_args()
    import torch
    import monai
    import dipy
    import ants
    import numpy as np
    from monai.networks.nets import AttentionUnet
    from dipy.nn.torch.synthseg import Model

    torch.set_num_threads(2)
    torch.manual_seed(0)
    report = {'python': sys.version, 'platform': platform.platform(),
              'runtime': sys.executable, 'torch': torch.__version__,
              'monai': monai.__version__, 'dipy': dipy.__version__,
              'antspyx': ants.__version__, 'device': 'cpu', 'checks': {}}
    models = [
        ('glioma_attention_unet3d', AttentionUnet(
            spatial_dims=3, in_channels=4, out_channels=3,
            channels=(32, 64, 128, 256, 512), strides=(2, 2, 2, 2), dropout=0.1),
         'best_model.pth', (1, 4, 32, 32, 32)),
        ('anatomy_synthseg', Model(model_scale=24, n_levels=5, output_channels=33),
         'synthseg_model_weights.pth', (1, 1, 32, 32, 32)),
    ]
    for model_id, model, weight, shape in models:
        start = time.perf_counter()
        checkpoint = torch.load(ROOT / 'models' / model_id / weight,
                                weights_only=True, map_location='cpu')
        state = checkpoint.get('model_state_dict', checkpoint)
        match = model.load_state_dict(state, strict=True)
        model.eval()
        with torch.inference_mode():
            output = model(torch.randn(shape))
        if not torch.isfinite(output).all():
            raise ValueError(f'Saída não finita: {model_id}')
        report['checks'][model_id] = {
            'strict_state_dict': str(match), 'weight_tensors': len(state),
            'parameters': sum(p.numel() for p in model.parameters()),
            'input_shape': list(shape), 'output_shape': list(output.shape),
            'all_finite': True, 'seconds': time.perf_counter() - start,
            'checkpoint_metadata': {k: v for k, v in checkpoint.items()
                                    if k != 'model_state_dict' and isinstance(v, (str, int, float, bool))},
        }
        print(json.dumps({model_id: report['checks'][model_id]}), flush=True)
    # Asymmetric synthetic blobs with a known physical grid; no public exam.
    grid = np.indices((32, 32, 32), dtype=float)
    blob = np.exp(-sum((grid[i] - c) ** 2 for i, c in enumerate((12, 17, 15))) / 30)
    blob += 0.4 * np.exp(-sum((grid[i] - c) ** 2 for i, c in enumerate((23, 11, 19))) / 10)
    fixed = ants.from_numpy(blob.astype('float32'))
    moving = ants.from_numpy(np.roll(blob, 2, axis=0).astype('float32'))
    labels = ants.from_numpy((np.roll(blob, 2, axis=0) > 0.3).astype('float32'))
    start = time.perf_counter()
    registration = ants.registration(
        fixed=fixed, moving=moving, type_of_transform='SyN',
        aff_iterations=(40, 20, 0), aff_shrink_factors=(4, 2, 1),
        aff_smoothing_sigmas=(2, 1, 0), reg_iterations=(10, 5, 0),
        random_seed=2026, outprefix=str(ROOT / 'runtime/model_assets_v1_ants_'),
        verbose=False)
    propagated = ants.apply_transforms(
        fixed=fixed, moving=labels, transformlist=registration['fwdtransforms'],
        interpolator='genericLabel')
    report['checks']['ants_synthetic'] = {
        'seconds': time.perf_counter() - start,
        'shape': list(propagated.shape),
        'labels': [float(v) for v in np.unique(propagated.numpy())],
        'all_finite': bool(np.isfinite(propagated.numpy()).all()),
        'forward_transforms': registration['fwdtransforms'],
        'inverse_transforms': registration['invtransforms'],
        'note': 'Compatibility smoke only; not an anatomical registration validation.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Relatório: {args.output}', flush=True)


if __name__ == '__main__':
    main()

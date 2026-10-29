"""Synthetic authorized multisequence inputs, with explicit physical transforms."""
from pathlib import Path
import numpy as np
import SimpleITK as sitk
from neuro_rt.adapters.base import ModelRunContext
from neuro_rt.imaging import geometry
from neuro_rt.model_registry import get_model_spec
from neuro_rt.study_types import InputBinding, SeriesDescriptor


def context_for(root, model_id, models_dir=None, shape=(24, 28, 32)):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    spec = get_model_spec(model_id)
    paths, series, bindings, transforms = {}, {}, [], {}
    z, y, x = np.indices(shape)
    blob = np.exp(-(((x-shape[2]/2)/9)**2 + ((y-shape[1]/2)/8)**2 + ((z-shape[0]/2)/7)**2))
    for i, entry in enumerate(spec['channels']):
        data = (blob * (100+i*19) + ((x+y+z) % 7) * .4).astype(np.float32)
        data[blob < .015] = 0
        image = sitk.GetImageFromArray(data)
        image.SetSpacing((1.3, 1.1, 1.7))
        image.SetOrigin((31., -47., 19.))
        image.SetDirection((0., -1., 0., 1., 0., 0., 0., 0., 1.))
        ticket = entry['role']
        path = root / f'{ticket}.nii.gz'
        sitk.WriteImage(image, str(path))
        series[ticket] = SeriesDescriptor(ticket, '', 'synthetic', 'same_moment', 'MR',
                                          geometry(image), source_format='nifti')
        paths[ticket] = path
        bindings.append(InputBinding(ticket, ticket, 'certain'))
        transform = root / f'{ticket}.tfm'
        sitk.WriteTransform(sitk.Transform(3, sitk.sitkIdentity), str(transform))
        transforms[ticket] = transform
    ref = series[spec['reference_role']]
    return ModelRunContext(spec, bindings, ref, series, paths, root / 'job',
        Path(models_dir or root / 'models'), 'cpu', source_to_reference=transforms,
        allow_legacy_models=True)

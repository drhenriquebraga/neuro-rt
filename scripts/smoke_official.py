"""Prova técnica com fantoma sintético, sem significado clínico."""
import json
from pathlib import Path

import numpy as np
import SimpleITK as sitk

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / 'runtime' / 'official_smoke'
folder.mkdir(parents=True, exist_ok=True)
z, y, x = np.mgrid[-1:1:48j, -1:1:52j, -1:1:48j]
radius = (x/.85)**2 + (y/.9)**2 + (z/.95)**2
rng = np.random.default_rng(42)
array = np.where(radius < .8, 80 + rng.normal(0,8,radius.shape), 0)
array += np.where((radius > .8) & (radius < 1), 45 + rng.normal(0,4,radius.shape), 0)
array[20:24,31:35,25:29] += 90
image = sitk.GetImageFromArray(array.astype(np.float32))
image.SetSpacing((2.5,2.5,2.5))
image.SetOrigin((30.,-20.,10.))
sitk.WriteImage(image, str(folder / 'synthetic_mri.nii.gz'))
(folder / 'request.json').write_text(json.dumps({'model':'MRI_GBM',
    'input_path':str(folder / 'synthetic_mri.nii.gz'), 'explicit_request':True, 'device':'cpu'}))
print(str(folder))

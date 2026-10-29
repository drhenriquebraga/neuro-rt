import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
import SimpleITK as sitk
from test_pipeline import TEMP_ROOT


class ViewsTests(unittest.TestCase):
    def test_host_builds_planes_and_mesh_with_physical_geometry(self):
        root=Path(__file__).resolve().parents[1]
        config=json.loads((root/'neuro_rt.local.json').read_text())
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            folder=Path(tmp);(folder/'inputs').mkdir();(folder/'masks').mkdir()
            array=np.arange(12*16*18,dtype=np.float32).reshape((12,16,18))
            image=sitk.GetImageFromArray(array);image.SetSpacing((.8,1.2,2.));image.SetOrigin((20.,30.,40.))
            sitk.WriteImage(image,str(folder/'inputs/input0.nii.gz'))
            mask=sitk.GetImageFromArray((array>700).astype(np.uint8));mask.CopyInformation(image)
            sitk.WriteImage(mask,str(folder/'masks/Tumor.nii.gz'))
            (folder/'manifest.json').write_text(json.dumps({'schema':'neuro-rt/result/1','masks':[{'path':'masks/Tumor.nii.gz'}]}))
            proc=subprocess.run([config['host_python'],str(root/'neuro_rt/build_views.py'),'--job-dir',str(folder),'--host-app',config['host_app']],capture_output=True,timeout=90)
            self.assertEqual(proc.returncode,0,proc.stderr.decode(errors='replace')[-1500:])
            view=json.loads((folder/'views/view.json').read_text())
            self.assertEqual(set(view['planes']),{'axial','coronal','sagittal'})
            self.assertEqual(len(view['meshes']),1)
            self.assertTrue((folder/'views'/view['meshes'][0]['path']).stat().st_size>84)
            for name,plane in view['planes'].items():
                frame=folder/'views'/f'{name}_{plane["center"]:03d}.png'
                self.assertEqual(frame.read_bytes()[:8],b'\x89PNG\r\n\x1a\n')


if __name__=='__main__':unittest.main()

"""Synthetic geometry and artifact tests for the native v2 study viewer."""
import json
import os
from pathlib import Path
import subprocess
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET

import numpy as np
import SimpleITK as sitk

from neuro_rt.roi_registry import make_roi_identity

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'neuro_rt.local.json').read_text()) if (ROOT/'neuro_rt.local.json').is_file() else {}
TEMP_ROOT = ROOT / 'runtime' / 'test-tmp'
TEMP_ROOT.mkdir(parents=True,exist_ok=True)


class StudyViewsTests(unittest.TestCase):
    @unittest.skipUnless(CONFIG.get('host_python') and Path(CONFIG.get('host_python','')).is_file(), 'Runtime do host indisponível.')
    def test_oblique_independent_rois_and_public_artifact_names(self):
        with tempfile.TemporaryDirectory(prefix='neuro-synthetic-',dir=TEMP_ROOT) as tmp:
            job = Path(tmp); (job/'inputs').mkdir(); (job/'masks').mkdir()
            array = np.arange(9*10*11,dtype=np.float32).reshape((9,10,11))
            image = sitk.GetImageFromArray(array)
            image.SetSpacing((.8,1.2,2.)); image.SetOrigin((11.,22.,33.))
            angle = .3
            image.SetDirection((np.cos(angle),-np.sin(angle),0.,np.sin(angle),np.cos(angle),0.,0.,0.,1.))
            sitk.WriteImage(image,str(job/'inputs/reference.nii.gz'))
            masks = []
            for index, model in enumerate(('MRI_GBM','MRI_Metastasis')):
                bits = np.zeros_like(array,dtype=np.uint8); bits[2:7,3:8,3+index:8+index] = 1
                mask = sitk.GetImageFromArray(bits); mask.CopyInformation(image)
                path = job/'masks'/('mask%d.nii.gz'%index); sitk.WriteImage(mask,str(path))
                masks.append({'model_id':model,'status':'completed','masks':[{'model_id':model,'class_id':'tumor','path':str(path),'space':'reference'}]})
            manifest = {'schema':'neuro-rt/result/2','revision':1,'results':masks,'artifacts':[]}
            (job/'study-manifest.json').write_text(json.dumps(manifest))
            command = [CONFIG['host_python'],str(ROOT/'neuro_rt/build_study_views.py'),'--job-dir',str(job),'--host-app',CONFIG['host_app']]
            run = subprocess.run(command,capture_output=True,timeout=90)
            self.assertEqual(run.returncode,0,run.stderr.decode(errors='replace')[-2500:])
            scene = json.loads((job/'views/view.json').read_text())
            self.assertEqual(scene['orientation'],'LPS')
            self.assertEqual(len(scene['rois']),2)
            self.assertEqual(scene['rois'][0]['color'],list(make_roi_identity('MRI_GBM','tumor',1).color))
            self.assertNotEqual(scene['rois'][0]['mesh'],scene['rois'][1]['mesh'])
            for index, roi in enumerate(scene['rois']):
                payload = (job/'views'/roi['mesh']).read_bytes()
                self.assertGreater(len(payload),84)
                triangles = struct.unpack_from('<I',payload,80)[0]
                vertices = np.array([struct.unpack_from('<9f',payload,84+50*t+12)
                                     for t in range(triangles)]).reshape(-1,3)
                native_indices = ((vertices-np.asarray(image.GetOrigin())) @ np.asarray(image.GetDirection()).reshape(3,3)) / np.asarray(image.GetSpacing())
                np.testing.assert_allclose(native_indices.min(0),[2.5+index,2.5,1.5],atol=1e-5)
                np.testing.assert_allclose(native_indices.max(0),[7.5+index,7.5,6.5],atol=1e-5)
            for plane in scene['planes'].values():
                frame = ET.parse(job/'views'/plane['slices'][plane['center']]).getroot()
                self.assertEqual({g.get('data-roi') for g in frame.findall('{http://www.w3.org/2000/svg}g') if g.get('data-roi')},{'roi_000','roi_001'})
            published = json.loads((job/'study-manifest.json').read_text())['artifacts']
            self.assertEqual(len({a['logical_name'] for a in published}),len(published))
            self.assertTrue(all(a['path'] == 'views/'+a['logical_name'] for a in published))
            self.assertNotIn(str(job),json.dumps(scene))
            # Regeneration must replace the previous set rather than duplicate it.
            run = subprocess.run(command,capture_output=True,timeout=90)
            self.assertEqual(run.returncode,0,run.stderr.decode(errors='replace')[-1500:])
            self.assertEqual(len(json.loads((job/'study-manifest.json').read_text())['artifacts']),len(published))

    def test_rejects_external_or_missing_mask(self):
        from neuro_rt.build_study_views import _inside
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            job = Path(tmp).resolve()
            with self.assertRaises(ValueError): _inside(job,ROOT/'README.md')
            with self.assertRaises(ValueError): _inside(job,job/'missing.nii.gz')


if __name__ == '__main__': unittest.main()

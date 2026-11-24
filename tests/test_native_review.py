"""Persisted research phantom reopened through the native reconstruction adapter."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from xml.etree import ElementTree as ET

import numpy as np
import SimpleITK as sitk
from integration.neuro_native_review import NeuroReview, PLANES
from neuro_rt.build_study_views import build_study_views
from neuro_rt.result_store import ResultStore, sha256_file
from test_result_recovery import sample_manifest


@unittest.skipUnless(os.environ.get('NEURO_TEST_HOST_APP'), 'Requires the host reconstruction engine')
class NativeReview(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.job = self.root / 'jobs/study-1'
        self.ref = self.job / 'inputs/reference.nii.gz'
        self.ref.parent.mkdir(parents=True)
        self.mask = self.job / 'masks/tumor.nii.gz'
        self.mask.parent.mkdir()
        data = np.arange(7*9*11,dtype=np.float32).reshape(7,9,11)
        # Coronal acquisition, nonzero origin and anisotropic slices.
        image = sitk.GetImageFromArray(data)
        image.SetOrigin((14.,22.,-40.))
        image.SetDirection((1.,0.,0.,0.,0.,-1.,0.,1.,0.))
        image.SetSpacing((1.,1.2,2.))
        sitk.WriteImage(image, str(self.ref))
        labels = np.zeros(data.shape,dtype=np.uint8)
        labels[2:5, 3:7, 4:7] = 1
        mask = sitk.GetImageFromArray(labels)
        mask.CopyInformation(image)
        sitk.WriteImage(mask, str(self.mask))
        store = ResultStore(self.root)
        self.host = os.environ['NEURO_TEST_HOST_APP']
        self.review = NeuroReview(SimpleNamespace(studies=SimpleNamespace(store=store),
                                                  settings=SimpleNamespace(host_app=self.host)),lambda req:True)
        self.data = sample_manifest().to_dict()
        self.data['results'][0]['masks'][0]['path'] = str(self.mask)
        desc = self.data['reference']
        self.cache = {'series_index':{'ticket-1':desc},'authorized_inputs':{'ticket-1':str(self.ref)},
                      'input_hashes':{'ticket-1':sha256_file(self.ref)}}
        (self.job/'preparation-cache.json').write_text(json.dumps(self.cache))
        (self.job/'study-manifest.json').write_text(json.dumps(self.data))
        self.ticket = 'neuro:study-1:1'

    def test_saved_native_mprs_and_mesh_with_all_slices_and_roi_visibility(self):
        scene = build_study_views(self.job,self.host)
        self.review.store.save_manifest(json.loads((self.job/'study-manifest.json').read_text()))
        self.assertEqual(self.review.rows(10)[0]['bilhete'],self.ticket)
        state = self.review.state(self.ticket)
        self.assertEqual(state['forma'],[scene['planes'][p]['count'] for p in PLANES])
        self.assertEqual(state['modalidade'],'MR')
        name = self.review.structures(self.ticket)['estruturas'][0]['nome']
        for axis,p in enumerate(PLANES):
            plan=scene['planes'][p]
            for index in (0,plan['center'],plan['count']-1):
                pos = index / (plan['count']-1)
                orig = ET.parse(self.job/'views'/plan['slices'][index]).getroot()
                got = ET.fromstring(self.review.plane(self.ticket,axis,pos,True,[name]))
                self.assertEqual(ET.tostring(got),ET.tostring(orig))
                hidden = ET.fromstring(self.review.plane(self.ticket,axis,pos,True,[]))
                self.assertFalse(any('data-roi' in e.attrib for e in hidden.iter()))
        self.assertGreater(len(self.review.mesh(self.ticket,name)),84)
        self.assertTrue(self.review.cloud(self.ticket,[name])['itens'][0]['pontos'])
        _, _, _, assets, _ = self.review._revision(self.ticket)
        Path(assets[scene['rois'][0]['mesh']]['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError): self.review.mesh(self.ticket,name)
        with self.assertRaises(FileNotFoundError): self.review.state('neuro:study-1:2')

    def test_revision_with_only_nifti_requires_its_exact_anatomical_reference(self):
        self.review.store.save_manifest(self.data)
        self.cache['series_index']['ticket-1']['frame_of_reference_uid']='2.3.4'
        (self.job/'preparation-cache.json').write_text(json.dumps(self.cache))
        with self.assertRaises(ValueError): self.review.state(self.ticket)
        self.cache['series_index']['ticket-1']['frame_of_reference_uid']='1.2.4'
        (self.job/'preparation-cache.json').write_text(json.dumps(self.cache))
        self.assertEqual(self.review.state(self.ticket)['modalidade'],'MR')
        self.assertTrue(self.review.structures(self.ticket)['estruturas'])


if __name__ == '__main__':
    unittest.main()

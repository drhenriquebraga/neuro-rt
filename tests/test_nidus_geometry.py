"""Manual Nidus editing/export on synthetic oblique reference data only."""
from pathlib import Path
import sys
import tempfile
import unittest
import json
from types import SimpleNamespace

import numpy as np
import SimpleITK as sitk

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'RECON_3D/app'))
import radai_projection as N
from neuro_rt import nidus_geometry as G


class NidusGeometryTests(unittest.TestCase):
    def test_persistence_keeps_current_and_previous_only_and_cancellation_keeps_pointer(self):
        image = sitk.Image([15, 13, 9], sitk.sitkInt16)
        core = N.consenso(image, [{'lao':0,'cra':0,'pontos':[(15,15),(45,15),(45,45)]}],lado=64)
        candidate = G.NidusCandidate(core,50)
        base = Path(__file__).resolve().parents[1] / 'runtime/test-tmp'
        base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            folder = Path(temporary)
            for _ in range(5):
                candidate.save(folder)
                candidate.edit(0,2,[(0,0),(.4,0),(.4,.4)],'add')
            self.assertEqual({p.name for p in folder.glob('mask-*.bits')},{'mask-4.bits','mask-5.bits'})
            before = (folder/'candidate.json').read_bytes()
            def cancelled(): raise RuntimeError('synthetic cancellation')
            with self.assertRaises(RuntimeError): candidate.save(folder,checkpoint=cancelled)
            self.assertEqual((folder/'candidate.json').read_bytes(),before)
            self.assertTrue((folder/json.loads(before)['mask']).is_file())

    def test_existing_host_writer_roundtrips_an_oblique_manual_suggestion(self):
        for modality in ('CT','MR'):
            with self.subTest(modality=modality): self._host_writer_roundtrip(modality)

    def _host_writer_roundtrip(self, modality):
        import pydicom
        from synthetic_dicom import make_series
        from neuro_rt.imaging import load_input
        base = Path(__file__).resolve().parents[1] / 'runtime/test-tmp'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            root = Path(temporary)
            uid, frame = make_series(root / 'source', modality=modality)
            angle = np.deg2rad(21.)
            direction = np.array([[1., 0, 0], [0, np.cos(angle), -np.sin(angle)], [0, np.sin(angle), np.cos(angle)]])
            for z, file in enumerate(sorted((root / 'source').glob('*.dcm'))):
                ds = pydicom.dcmread(file)
                ds.ImageOrientationPatient = [*direction[:, 0], *direction[:, 1]]
                ds.ImagePositionPatient = list(np.array([20., 30., -11.]) + direction[:, 2]*z*2.)
                ds.save_as(file, enforce_file_format=True)
            image, source = load_input(root / 'source', uid, allowed_modalities=(modality,))
            mask = np.zeros(tuple(reversed(image.GetSize())), dtype=bool)
            mask[2:5, 5:11, 7:13] = True
            core = SimpleNamespace(geometry={key: list(value) for key, value in (
                ('size', image.GetSize()), ('spacing', image.GetSpacing()),
                ('origin', image.GetOrigin()), ('direction', image.GetDirection()))},
                eixos=N.eixos_lps(image), temperature=float,
                packed=lambda temperature, progress=None: N.compactar(mask))
            candidate = G.NidusCandidate(core, 42)
            output = G.export_candidate(candidate, root / 'source', uid,
                Path(__file__).resolve().parents[2] / 'AUTO_CONTORNO', root / 'result')
            written = pydicom.dcmread(output)
            self.assertEqual(str(written.ApprovalStatus), 'UNAPPROVED')
            self.assertEqual(written.ReferencedFrameOfReferenceSequence[0].FrameOfReferenceUID, frame)
            self.assertIn('manual', written.RTROIObservationsSequence[0].ROIObservationDescription.lower())
            self.assertEqual(len(list((root / 'source').glob('*.dcm'))), 8)

    def test_changed_source_identity_is_rejected_before_writing(self):
        import pydicom
        from synthetic_dicom import make_series
        base = Path(__file__).resolve().parents[1] / 'runtime/test-tmp'
        base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            root=Path(temporary)
            uid,_=make_series(root/'source',modality='CT')
            signature=G.source_signature(root/'source',uid)
            file=next((root/'source').glob('*.dcm'))
            ds=pydicom.dcmread(file);ds.PatientID='SYNTHETIC_CHANGED';ds.save_as(file,enforce_file_format=True)
            with self.assertRaisesRegex(ValueError,'referências DICOM mudaram'):
                G.export_candidate(None,root/'source',uid,root,root/'result',expected_signature=signature)
            self.assertFalse((root/'result').exists())

    def test_manual_plane_edit_and_undo_preserve_the_native_oblique_grid(self):
        image = sitk.Image([23, 17, 11], sitk.sitkInt16)
        image.SetSpacing((.7, 1.2, 2.))
        image.SetOrigin((20., -30., 40.))
        angle = np.deg2rad(20.)
        image.SetDirection((np.cos(angle), -np.sin(angle), 0., np.sin(angle), np.cos(angle), 0., 0., 0., 1.))
        core = N.consenso(image, [{'lao': 0, 'cra': 0, 'pontos': [(20,20),(43,20),(43,43),(20,43)]}], lado=64)
        for axis in range(3):
            candidate = G.NidusCandidate(core, 50)
            before = candidate.packed.bits.copy()
            count = candidate.view_shape[axis]
            index = count // 2
            polygon = [(0,0),(.45,0),(.45,.45),(0,.45)]
            candidate.edit(axis, index, polygon, 'add')
            self.assertTrue(candidate.edited)
            candidate.undo()
            np.testing.assert_array_equal(candidate.packed.bits, before)
            self.assertEqual(candidate.geometry['direction'], list(image.GetDirection()))

    def test_edit_rejects_nonfinite_outside_or_unknown_operations(self):
        image = sitk.Image([15, 13, 9], sitk.sitkInt16)
        core = N.consenso(image, [{'lao': 0, 'cra': 0, 'pontos': [(15,15),(45,15),(45,45)]}], lado=64)
        candidate = G.NidusCandidate(core, 30)
        for points, operation in (([(0,0),(1,0),(float('nan'),1)], 'add'),
                                  ([(0,0),(2,0),(1,1)], 'add'),
                                  ([(0,0),(1,0),(1,1)], 'replace')):
            with self.assertRaises(ValueError):
                candidate.edit(0, 1, points, operation)

    def test_edit_on_permuted_flipped_oblique_planes_matches_native_voxels(self):
        image = sitk.Image([23,17,11],sitk.sitkInt16)
        image.SetSpacing((.7,1.2,2.))
        angle = np.deg2rad(17.)
        rotation = np.array([[np.cos(angle),-np.sin(angle),0],
                             [np.sin(angle),np.cos(angle),0],[0,0,1.]])
        permutation = np.array([[0,0,-1.],[-1.,0,0],[0,1.,0]])
        image.SetDirection(tuple((rotation@permutation).ravel()))
        core = N.consenso(image,[{'lao':37,'cra':-13,'pontos':[(24,24),(38,24),(38,38)]}],lado=64)
        eixos = N.eixos_lps(image)
        self.assertNotEqual(eixos[0],(0,1,2))
        self.assertTrue(any(eixos[1]))
        for axis in range(3):
            candidate = G.NidusCandidate(core,50)
            view = N.para_lps(candidate.mask(),eixos).copy()
            index = view.shape[axis]//2
            before = N.corte(view,axis,index).copy()
            delta = N._mascara_poligono([(0,0),(before.shape[1]*.4,0),
                (before.shape[1]*.4,before.shape[0]*.4)],*before.shape)
            result = before|delta
            if axis==0: view[index]=result
            elif axis==1: view[:,index,:]=result[::-1]
            else: view[:,:,index]=result[::-1]
            for dimension,inverted in enumerate(eixos[1]):
                if inverted: view=np.flip(view,axis=dimension)
            expected = np.transpose(view,np.argsort(eixos[0]))
            candidate.edit(axis,index,[(0,0),(.4,0),(.4,.4)],'add')
            np.testing.assert_array_equal(candidate.mask(),expected)


if __name__ == '__main__':
    unittest.main()

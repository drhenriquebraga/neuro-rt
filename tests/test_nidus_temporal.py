"""Temporal angiography uses invented DICOMs; no clinical images or inference."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage, EnhancedMRImageStorage, generate_uid


def dataset(path, *, study, frame, uid, patient='SYNTHETIC_A', enhanced=False):
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = EnhancedMRImageStorage if enhanced else MRImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    ds = FileDataset(str(path), {}, file_meta=meta, preamble=bytes(128))
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID, ds.SeriesInstanceUID, ds.FrameOfReferenceUID = study, uid, frame
    ds.PatientID = patient
    ds.IssuerOfPatientID = 'SYNTHETIC_SITE'
    ds.Modality, ds.ImageType = 'MR', ['ORIGINAL', 'PRIMARY']
    ds.Rows, ds.Columns = 5, 6
    ds.SamplesPerPixel, ds.PhotometricInterpretation = 1, 'MONOCHROME2'
    ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 16, 16, 15, 0
    ds.ImageOrientationPatient, ds.PixelSpacing = [1, 0, 0, 0, 1, 0], [.8, .7]
    ds.ProtocolName, ds.MRAcquisitionType = 'SYNTHETIC TRICKS', '3D'
    return ds


def classic(folder, *, temporal=True, separate=False, time_only=False, patient='SYNTHETIC_A',
            mismatch=None, static_tof=False, projection=False):
    study, frame, uid = generate_uid(), generate_uid(), generate_uid()
    sources = []
    for phase in range(3):
        phase_uid = generate_uid() if separate else uid
        for z in range(1 if projection else 3):
            path = folder / ('p%d-z%d.dcm' % (phase, z))
            ds = dataset(path, study=study, frame=frame, uid=phase_uid,
                         patient=('SYNTHETIC_B' if mismatch == 'patient' and phase == 2 else patient))
            ds.SeriesDescription = 'AXI 3D TOF 3SLAB FS MT ASSET' if static_tof else 'TRICKS dynamic'
            if static_tof:
                ds.ProtocolName = '3D TOF'
            ds.InstanceNumber = phase * 3 + z + 1
            ds.ImagePositionPatient = [0, 0, z * 2.0]
            if temporal and not time_only:
                ds.TemporalPositionIdentifier = phase + 1
                ds.NumberOfTemporalPositions = 3
            ds.AcquisitionNumber = phase + 1
            ds.AcquisitionDateTime = '202611121000%02d' % (phase * 2)
            if projection:
                ds.ImageType = ['DERIVED', 'SECONDARY', 'MIP']
            if mismatch == 'grid' and phase == 2:
                ds.PixelSpacing = [.9, .7]
            if mismatch == 'frame' and phase == 2:
                ds.FrameOfReferenceUID = generate_uid()
            if mismatch == 'missing' and phase == 2 and z == 1:
                continue
            if mismatch == 'variable_time':
                ds.AcquisitionDateTime = '202611121000%02d' % (phase * 6 + z)
            ds.PixelData = np.full((5, 6), 50 + phase * 100 + z, dtype='<u2').tobytes()
            ds.save_as(path, enforce_file_format=True)
        if phase_uid not in [s['uid'] for s in sources]:
            sources.append({'ticket': 'ticket%d' % phase, 'folder': str(folder), 'uid': phase_uid})
    return sources


def enhanced(folder, *, temporal=True):
    path = folder / 'enhanced.dcm'
    ds = dataset(path, study=generate_uid(), frame=generate_uid(), uid=generate_uid(), enhanced=True)
    ds.NumberOfFrames = 9
    shared = Dataset()
    orient, measures = Dataset(), Dataset()
    orient.ImageOrientationPatient = ds.ImageOrientationPatient
    measures.PixelSpacing, measures.SliceThickness = ds.PixelSpacing, 2.0
    shared.PlaneOrientationSequence = Sequence([orient])
    shared.PixelMeasuresSequence = Sequence([measures])
    ds.SharedFunctionalGroupsSequence = Sequence([shared])
    frames, pixels = [], []
    for phase in range(3):
        for z in range(3):
            fg, content, pos = Dataset(), Dataset(), Dataset()
            if temporal:
                content.TemporalPositionIndex = phase + 1
            content.StackID, content.InStackPositionNumber = '1', z + 1
            content.FrameAcquisitionDateTime = '202611121000%02d' % (phase * 2)
            fg.FrameContentSequence = Sequence([content])
            pos.ImagePositionPatient = [0, 0, z * 2.0]
            fg.PlanePositionSequence = Sequence([pos])
            frames.append(fg)
            pixels.append(np.full((5, 6), phase * 100 + z, dtype='<u2'))
    ds.PerFrameFunctionalGroupsSequence = Sequence(frames)
    ds.PixelData = np.stack(pixels).tobytes()
    ds.save_as(path, enforce_file_format=True)
    return [{'ticket': 'enhanced-ticket', 'folder': str(folder), 'uid': str(ds.SeriesInstanceUID)}]


class TemporalDiscovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from neuro_rt import nidus_temporal
        cls.module = nidus_temporal

    def test_classic_temporal_index_orders_complete_volumes_and_no_phi(self):
        with tempfile.TemporaryDirectory() as temp:
            sources = classic(Path(temp))
            result = self.module.discover(sources)
            self.assertEqual(len(result.groups), 1)
            group = result.groups[0]
            self.assertEqual(group.kind, 'volume3d')
            self.assertEqual(len(group.frames), 3)
            self.assertEqual([f.time_seconds for f in group.frames], [0, 2, 4])
            a = self.module.load_frame(group, 2)
            self.assertEqual(a.array.shape, (3, 5, 6))
            np.testing.assert_array_equal(a.array[:, 0, 0], [250, 251, 252])
            public = json.dumps(group.public())
            self.assertNotIn('SYNTHETIC_A', public)
            self.assertNotIn(temp, public)
            self.assertNotIn(sources[0]['uid'], public)

    def test_static_tof_and_rotating_mip_are_not_dynamic_by_file_order(self):
        for projection in (False, True):
            with self.subTest(projection=projection), tempfile.TemporaryDirectory() as temp:
                sources = classic(Path(temp), temporal=False, static_tof=True, projection=projection)
                self.assertEqual(self.module.discover(sources).groups, [])

    def test_mixed_identity_or_frame_cannot_become_a_partial_cine(self):
        for bad in ('patient', 'frame', 'grid', 'missing'):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as temp:
                result = self.module.discover(classic(Path(temp), mismatch=bad))
                self.assertEqual(result.groups, [])
                self.assertTrue(result.rejected)

    def test_multiple_uid_dynamic_acquisitions_require_real_consistent_times(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.module.discover(classic(Path(temp), separate=True, time_only=True))
            self.assertEqual(len(result.groups), 1)
            self.assertEqual(result.groups[0].evidence, 'dynamic_acquisition')
        with tempfile.TemporaryDirectory() as temp:
            result = self.module.discover(classic(Path(temp), separate=True, time_only=True, mismatch='variable_time'))
            self.assertEqual(result.groups, [])

    def test_adjacent_stacks_from_distinct_series_cannot_be_stitched_into_one_phase(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            sources = classic(folder)
            other_uid = generate_uid()
            for path in list(folder.glob('*.dcm')):
                ds = pydicom.dcmread(path)
                ds.SeriesInstanceUID = other_uid
                ds.SOPInstanceUID = generate_uid()
                ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
                ds.ImagePositionPatient = [0, 0, float(ds.ImagePositionPatient[2]) + 6]
                ds.AcquisitionDateTime = '202611121005%02d' % ((int(ds.TemporalPositionIdentifier) - 1) * 2)
                ds.save_as(folder / ('other-' + path.name), enforce_file_format=True)
            sources.append({'folder': temp, 'uid': other_uid})
            result = self.module.discover(sources)
            self.assertEqual(result.groups, [])
            self.assertIn('MIXED_SERIES_IN_PHASE', [r['code'] for r in result.rejected])

    def test_distinct_complete_series_for_each_temporal_index_remain_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.module.discover(classic(Path(temp), separate=True))
            self.assertEqual(len(result.groups), 1)
            self.assertEqual(len(result.groups[0].frames), 3)
            self.assertEqual([len(frame.planes) for frame in result.groups[0].frames], [3, 3, 3])

    def test_enhanced_mr_uses_frame_index_and_physical_geometry(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.module.discover(enhanced(Path(temp)))
            self.assertEqual(len(result.groups), 1)
            a = self.module.load_frame(result.groups[0], 1)
            np.testing.assert_array_equal(a.array[:, 0, 0], [100, 101, 102])
            self.assertEqual(a.spacing, (.7, .8, 2.0))
            self.assertEqual(a.origin, (0., 0., 0.))
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(self.module.discover(enhanced(Path(temp), temporal=False)).groups, [])

    def test_two_dimensional_temporal_mips_are_not_rotatable_volumes(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.module.discover(classic(Path(temp), projection=True))
            self.assertEqual(result.groups[0].kind, 'projection2d')
            self.assertFalse(result.groups[0].public()['can_rotate'])
            self.assertEqual(self.module.load_frame(result.groups[0], 0).array.ndim, 2)

    def test_enhanced_global_start_time_does_not_override_real_temporal_indices(self):
        with tempfile.TemporaryDirectory() as temp:
            sources = enhanced(Path(temp))
            path = Path(temp) / 'enhanced.dcm'
            ds = pydicom.dcmread(path)
            for fg in ds.PerFrameFunctionalGroupsSequence:
                fg.FrameContentSequence[0].FrameAcquisitionDateTime = '20261112100000'
            ds.save_as(path, enforce_file_format=True)
            group = self.module.discover(sources).groups[0]
            self.assertFalse(group.public()['timing_known'])
            self.assertEqual([f.time_seconds for f in group.frames], [None, None, None])
            ds.TemporalResolution = 1500
            ds.save_as(path, enforce_file_format=True)
            group = self.module.discover(sources).groups[0]
            self.assertEqual([f.time_seconds for f in group.frames], [0, 1.5, 3])

    def test_shared_scale_retains_different_phase_intensities(self):
        with tempfile.TemporaryDirectory() as temp:
            group = self.module.discover(classic(Path(temp))).groups[0]
            data = [self.module.load_frame(group, i) for i in range(3)]
            scale = self.module.shared_scale([self.module.sample_values(d) for d in data])
            self.assertEqual(scale['min'], 50)
            self.assertEqual(scale['max'], 252)
            self.assertIn(99.95, scale['percentis'])
            self.assertIn(99.99, scale['percentis'])

    def test_monochrome1_volume_is_not_silently_treated_as_bright_vessel_mip(self):
        with tempfile.TemporaryDirectory() as temp:
            sources = classic(Path(temp))
            for path in Path(temp).glob('*.dcm'):
                ds = pydicom.dcmread(path)
                ds.PhotometricInterpretation = 'MONOCHROME1'
                ds.save_as(path, enforce_file_format=True)
            result = self.module.discover(sources)
            self.assertEqual(result.groups, [])
            self.assertIn('UNSUPPORTED_VOLUME_POLARITY', [r['code'] for r in result.rejected])

    def test_changed_source_invalidates_registered_group(self):
        with tempfile.TemporaryDirectory() as temp:
            group = self.module.discover(classic(Path(temp))).groups[0]
            path = Path(temp) / 'p0-z0.dcm'
            path.write_bytes(path.read_bytes() + b'changed')
            with self.assertRaises(self.module.TemporalError) as error:
                self.module.load_frame(group, 0)
            self.assertEqual(error.exception.code, 'SOURCE_CHANGED')


if __name__ == '__main__':
    unittest.main()

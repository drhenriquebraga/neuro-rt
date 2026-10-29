from pathlib import Path

import numpy as np
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage, generate_uid


def make_series(folder, modality='MR', slices=8, z_offset=0, uid=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    series_uid = uid or generate_uid()
    study_uid, frame_uid = generate_uid(), generate_uid()
    for z in range(slices):
        meta = FileMetaDataset()
        meta.MediaStorageSOPClassUID = MRImageStorage
        meta.MediaStorageSOPInstanceUID = generate_uid()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        meta.ImplementationClassUID = generate_uid()
        path = folder / f'{series_uid[-8:]}_{z:03d}.dcm'
        ds = FileDataset(str(path), {}, file_meta=meta, preamble=b'\0' * 128)
        ds.SOPClassUID = meta.MediaStorageSOPClassUID
        ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = series_uid
        ds.FrameOfReferenceUID = frame_uid
        ds.PatientName = 'SYNTHETIC^NEURO'
        ds.PatientID = 'SYNTHETIC'
        ds.PatientBirthDate = ''
        ds.PatientSex = ''
        ds.StudyID = '1'
        ds.StudyDate = '20261011'
        ds.StudyTime = '120000'
        ds.SeriesNumber = 1
        ds.Modality = modality
        ds.InstanceNumber = z + 1
        ds.ImagePositionPatient = [20., 30., z_offset + z * 2.]
        ds.ImageOrientationPatient = [1., 0., 0., 0., 1., 0.]
        ds.Rows = ds.Columns = 16
        ds.PixelSpacing = [1.2, .8]
        ds.SliceThickness = 2.
        ds.BitsAllocated = ds.BitsStored = 16
        ds.HighBit = 15
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = 'MONOCHROME2'
        ds.PixelRepresentation = 0
        ds.PixelData = np.full((16, 16), z + 100, dtype=np.uint16).tobytes()
        ds.save_as(path, enforce_file_format=True)
    return series_uid, frame_uid

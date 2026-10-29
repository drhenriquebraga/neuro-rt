from pathlib import Path

import numpy as np
import pydicom
import SimpleITK as sitk


def geometry(image):
    return {'size_xyz': list(image.GetSize()), 'spacing_xyz_mm': list(image.GetSpacing()),
            'origin_lps_mm': list(image.GetOrigin()), 'direction_lps': list(image.GetDirection())}


def check_volume(image):
    if image.GetDimension() != 3 or image.GetNumberOfComponentsPerPixel() != 1:
        raise ValueError('A entrada precisa ser um volume escalar 3D.')
    if min(image.GetSize()) < 2 or min(image.GetSpacing()) <= 0:
        raise ValueError('Volume sem geometria 3D válida.')
    if not np.isfinite(sitk.GetArrayViewFromImage(image)).all():
        raise ValueError('Volume contém valores não finitos.')


def dicom_series(folder):
    reader = sitk.ImageSeriesReader()
    ids = reader.GetGDCMSeriesIDs(str(folder)) or []
    series = []
    for uid in ids:
        files = list(reader.GetGDCMSeriesFileNames(str(folder), uid))
        if not files:
            continue
        ds = pydicom.dcmread(files[0], stop_before_pixels=True,
                            specific_tags=['Modality'])
        if str(ds.get('Modality', '')) == 'MR':
            series.append({'uid': uid, 'slices': len(files), 'modality': 'MR'})
    return series


def load_input(path, uid=''):
    path = Path(path)
    if path.is_file() and (path.name.lower().endswith('.nii.gz') or path.suffix.lower() == '.nii'):
        image = sitk.ReadImage(str(path))
        source = {'kind': 'nifti', 'dicom_files': [], 'series_uid': '', 'frame_uid': ''}
    elif path.is_dir():
        series = dicom_series(path)
        if not uid:
            if len(series) != 1:
                raise ValueError('Selecione uma única série MR pelo SeriesInstanceUID.')
            uid = series[0]['uid']
        if uid not in [s['uid'] for s in series]:
            raise ValueError('A série escolhida não é uma série MR desta pasta.')
        reader = sitk.ImageSeriesReader()
        files = list(reader.GetGDCMSeriesFileNames(str(path), uid))
        tags = ['ImagePositionPatient', 'ImageOrientationPatient', 'PixelSpacing',
                'FrameOfReferenceUID', 'SOPInstanceUID', 'SeriesInstanceUID', 'NumberOfFrames',
                'Rows', 'Columns']
        datasets = [pydicom.dcmread(f, stop_before_pixels=True, specific_tags=tags) for f in files]
        if len(datasets) < 2 or any(int(ds.get('NumberOfFrames', 1)) != 1 for ds in datasets):
            raise ValueError('Use série MR 3D com arquivos de corte único; multiframe não é suportado.')
        first = datasets[0]
        required = tags[:6] + ['Rows', 'Columns']
        if any(tag not in first for tag in required):
            raise ValueError('DICOM sem geometria e referências completas.')
        orientation = np.array(first.ImageOrientationPatient, dtype=float)
        normal = np.cross(orientation[:3], orientation[3:])
        if not np.allclose(np.linalg.norm(normal), 1., atol=1e-5):
            raise ValueError('Orientação DICOM inválida.')
        positions = []
        for ds in datasets:
            if (any(tag not in ds for tag in required) or
                ds.FrameOfReferenceUID != first.FrameOfReferenceUID or
                not np.allclose(ds.ImageOrientationPatient, orientation, atol=1e-5) or
                not np.allclose(ds.PixelSpacing, first.PixelSpacing, atol=1e-5) or
                (ds.Rows, ds.Columns) != (first.Rows, first.Columns)):
                raise ValueError('A série mistura grades ou Frames of Reference.')
            positions.append(np.array(ds.ImagePositionPatient, dtype=float))
        deltas = np.diff(positions, axis=0)
        steps = deltas @ normal
        if (np.any(steps <= 1e-4) or not np.allclose(steps, steps[0], atol=.02, rtol=.01) or
            not np.allclose(deltas, np.outer(steps, normal), atol=.02)):
            raise ValueError('Série MR irregular, cortes duplicados ou inclinados; geometria não aceita.')
        if len({str(ds.SOPInstanceUID) for ds in datasets}) != len(files):
            raise ValueError('SOPInstanceUID duplicado na série.')
        reader.SetFileNames(files)
        image = reader.Execute()
        source = {'kind': 'dicom', 'dicom_files': files, 'series_uid': uid,
                  'frame_uid': str(first.FrameOfReferenceUID),
                  'sop_uids': [str(ds.SOPInstanceUID) for ds in datasets]}
    else:
        raise ValueError('Caminho não existe ou não é NIfTI/pasta DICOM.')
    check_volume(image)
    return image, source


def validate_mask(mask, reference):
    check_volume(mask)
    if (mask.GetSize() != reference.GetSize() or
        any(not np.allclose(a, b, atol=1e-4, rtol=0) for a, b in
            ((mask.GetSpacing(), reference.GetSpacing()),
             (mask.GetOrigin(), reference.GetOrigin()),
             (mask.GetDirection(), reference.GetDirection())))):
        raise ValueError('Máscara fora da geometria da RM de origem; não será exportada.')
    array = sitk.GetArrayViewFromImage(mask)
    if not np.isin(array, [0, 1]).all():
        raise ValueError('Saída não é uma máscara binária; probabilidades não viram contorno.')
    voxels = int(np.count_nonzero(array))
    return {'voxels': voxels, 'volume_cm3': voxels * float(np.prod(mask.GetSpacing())) / 1000}

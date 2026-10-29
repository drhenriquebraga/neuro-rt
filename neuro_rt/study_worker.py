"""Private CLI called by the host coordinator, never by an HTTP-supplied command."""
from .scientific_io import write_image, write_transform
import argparse
from dataclasses import replace
import json
from pathlib import Path
import shutil
import traceback


def _check_headers(headers, descriptor):
    import numpy as np
    required = ('ImagePositionPatient', 'ImageOrientationPatient', 'PixelSpacing',
                'Rows', 'Columns', 'SeriesInstanceUID', 'SOPInstanceUID',
                'FrameOfReferenceUID', 'StudyInstanceUID', 'PatientID', 'Modality')
    if any(any(tag not in ds for tag in required) for ds in headers):
        raise ValueError('DICOM sem geometria e identidade completas.')
    first = headers[0]
    identity = tuple(str(first.get(k, '')) for k in ('PatientID', 'IssuerOfPatientID', 'StudyInstanceUID'))
    if any(tuple(str(ds.get(k, '')) for k in ('PatientID', 'IssuerOfPatientID', 'StudyInstanceUID'))
           != identity for ds in headers):
        raise ValueError('A série mistura sujeitos ou estudos.')
    if (any(str(ds.SeriesInstanceUID) != descriptor.series_uid for ds in headers)
            or len({str(ds.SOPInstanceUID) for ds in headers}) != len(headers)
            or {str(ds.SOPInstanceUID) for ds in headers} != set(descriptor.sop_instance_uids)
            or any(str(ds.FrameOfReferenceUID) != descriptor.frame_of_reference_uid
                   or str(ds.Modality) != descriptor.modality for ds in headers)):
        raise ValueError('A série DICOM mudou após a seleção.')
    orientation = np.asarray(first.ImageOrientationPatient, dtype=float)
    spacing = np.asarray(first.PixelSpacing, dtype=float)
    if (orientation.shape != (6,) or spacing.shape != (2,)
            or not np.isfinite(orientation).all() or not np.isfinite(spacing).all()
            or np.any(spacing <= 0) or min(int(first.Rows), int(first.Columns)) < 2
            or not np.allclose(np.linalg.norm(orientation.reshape(2, 3), axis=1), 1, atol=1e-5)
            or not np.isclose(np.dot(orientation[:3], orientation[3:]), 0, atol=1e-5)):
        raise ValueError('Geometria DICOM inválida.')
    positions = []
    for ds in headers:
        position = np.asarray(ds.ImagePositionPatient, dtype=float)
        if (position.shape != (3,) or not np.isfinite(position).all()
                or not np.allclose(ds.ImageOrientationPatient, orientation, atol=1e-5)
                or not np.allclose(ds.PixelSpacing, spacing, atol=1e-5)
                or (ds.Rows, ds.Columns) != (first.Rows, first.Columns)
                or int(ds.get('NumberOfFrames', 1)) != 1):
            raise ValueError('A série mistura grades ou contém geometria inválida.')
        positions.append(position)
    normal = np.cross(orientation[:3], orientation[3:])
    positions = np.asarray(positions)
    positions = positions[np.argsort(positions @ normal)]
    deltas = np.diff(positions, axis=0)
    steps = deltas @ normal
    if (np.any(steps <= 1e-4) or not np.allclose(steps, steps[0], atol=.02, rtol=.01)
            or not np.allclose(deltas, np.outer(steps, normal), atol=.02)):
        raise ValueError('Série DICOM irregular, duplicada ou inclinada.')
    return identity


def prepare(job_dir):
    import numpy as np
    import pydicom
    import SimpleITK as sitk
    from integration.host_imports import prepare_host_imports
    from .imaging import check_volume, geometry
    from .geometry_pipeline import _validate_transform, _inverse_transform, verify_reference_geometry
    from .series_selection import describe_series
    from types import SimpleNamespace
    from .study_service import atomic_json
    data = json.loads((job_dir / 'input-sources.json').read_text(encoding='utf-8'))
    prepare_host_imports(data['host_app'])
    import engine
    inputs = job_dir / 'inputs'
    inputs.mkdir(exist_ok=True)
    images, paths, transforms, errors = {}, {}, {}, {}
    index = {ticket: describe_series(ticket, SimpleNamespace(resolve_series_ticket=lambda t, r=record: r))
             for ticket, record in data['sources'].items()}
    def failed(ticket, stage, error):
        errors.setdefault(ticket, []).append({'stage': stage, 'error': ''.join(traceback.format_exception(error))})
        atomic_json(job_dir / 'preparation-errors.json', errors)
    reference_identity = None
    # Load the mandatory reference first, even if the source map has another order.
    tickets = [data['reference'], *(t for t in data['sources'] if t != data['reference'])]
    for number, ticket in enumerate(tickets):
        try:
            descriptor = index[ticket]
            source = data['sources'][ticket]['source']
            if source.get('kind', 'dicom') != 'dicom':
                raise ValueError('O seletor integrado exige séries DICOM autorizadas.')
            folder, uid = source['input_path'], descriptor.series_uid
            files = list(source['dicom_files'])
            if len(files) < 2: raise ValueError('A série precisa ter cortes suficientes para um volume 3D.')
            headers = [pydicom.dcmread(f, stop_before_pixels=True) for f in files]
            identity = _check_headers(headers, descriptor)
            if ticket != data['reference']:
                ref = index[data['reference']]
                if (identity != reference_identity or descriptor.subject_key != ref.subject_key
                        or descriptor.study_key != ref.study_key or descriptor.modality != ref.modality):
                    raise ValueError('O alinhamento exige mesmo sujeito, estudo e modalidade.')
            # Reuse the same reader as Nidus, Recon3D and ContourLab.
            image = engine.load_sitk(folder, uid)
            check_volume(image)
            if not verify_reference_geometry(image, image).valid:
                raise ValueError('O volume contém geometria não finita.')
            descriptor = replace(descriptor, geometry=geometry(image))
            destination = inputs / ('reference.nii.gz' if ticket == data['reference'] else f'series_{number}.nii.gz')
            write_image(image, str(destination))
            images[ticket], index[ticket], paths[ticket] = image, descriptor, str(destination)
            if ticket == data['reference']:
                reference_identity = identity
                original = job_dir / 'dicom_source'
                original.mkdir(exist_ok=True)
                for n, path in enumerate(files): shutil.copyfile(path, original / f'{n:06d}.dcm')
                atomic_json(job_dir / 'source.json', {'kind': 'dicom', 'dicom_files': files,
                    'input_path': folder, 'series_uid': uid, 'modality': descriptor.modality,
                    'frame_uid': descriptor.frame_of_reference_uid, 'sop_uids': descriptor.sop_instance_uids})
        except Exception as error:
            failed(ticket, 'load', error)
            if ticket == data['reference']: raise
    reference = images[data['reference']]
    transform_dir = job_dir / 'transforms'; transform_dir.mkdir(exist_ok=True)
    for ticket, image in images.items():
        if ticket == data['reference']: continue
        # Rigid intra-exam registration. SITK optimizes reference->source;
        # the common geometry contract stores source->reference explicitly.
        try:
            method = sitk.ImageRegistrationMethod()
            method.SetMetricAsMattesMutualInformation(32)
            method.SetMetricSamplingStrategy(method.REGULAR)
            method.SetMetricSamplingPercentage(.2, 20261029)
            method.SetInterpolator(sitk.sitkLinear)
            method.SetOptimizerAsGradientDescent(learningRate=1., numberOfIterations=120,
                convergenceMinimumValue=1e-6, convergenceWindowSize=10)
            method.SetOptimizerScalesFromPhysicalShift()
            method.SetShrinkFactorsPerLevel([4, 2, 1])
            method.SetSmoothingSigmasPerLevel([2, 1, 0]); method.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()
            fixed, moving = sitk.Cast(reference, sitk.sitkFloat32), sitk.Cast(image, sitk.sitkFloat32)
            initial = sitk.CenteredTransformInitializer(fixed, moving, sitk.Euler3DTransform(),
                        sitk.CenteredTransformInitializerFilter.GEOMETRY)
            method.SetInitialTransform(initial, inPlace=False)
            optimized = method.Execute(fixed, moving)
            if not np.isfinite(method.GetMetricValue()): raise ValueError('O registro não convergiu para uma métrica válida.')
            _validate_transform(optimized, 3)
            inverse = _inverse_transform(optimized, 3)
            _validate_transform(inverse, 3)
            file = transform_dir / f'{len(transforms)}.tfm'
            write_transform(inverse, str(file))
            transforms[ticket] = str(file)
        except Exception as error:
            failed(ticket, 'registration', error)
    atomic_json(job_dir / 'prepared-inputs.json', {'series_index': {t: d.to_dict() for t, d in index.items()},
        'authorized_inputs': paths, 'source_to_reference': transforms})


def model(job_dir):
    from .adapter_registry import ADAPTER_FACTORIES
    from .adapters.base import ModelRunContext
    from .study_types import SeriesDescriptor, InputBinding
    from .contracts import validate_model_result, validate_worker_progress
    from .study_service import atomic_json
    data = json.loads((job_dir / 'model-context.json').read_text(encoding='utf-8'))
    spec = data['model_spec']
    factory = ADAPTER_FACTORIES.get(spec['adapter_id'])
    if factory is None: raise ValueError('Adaptador não pertence ao registro desta versão.')
    sequence = 0
    def progress(stage, fraction):
        nonlocal sequence
        sequence += 1
        event = validate_worker_progress({'seq': sequence, 'stage': stage, 'fraction': fraction})
        atomic_json(job_dir / 'worker-progress.json', event)
    context = ModelRunContext(spec, [InputBinding(**b) for b in data['bindings']],
        SeriesDescriptor(**data['reference']),
        {t: SeriesDescriptor(**d) for t, d in data['series_index'].items()},
        {t: Path(p) for t, p in data['authorized_inputs'].items()},
        job_dir, Path(data['models_dir']), data['device'],
        progress=progress,
        source_to_reference={t: Path(p) for t, p in data['source_to_reference'].items()},
        allow_legacy_models=data.get('allow_legacy_models', False),
        host_app=Path(data['host_app']) if data.get('host_app') else None,
        host_python=Path(data['host_python']) if data.get('host_python') else None,
        study_id=data.get('study_id', ''))
    adapter = factory()
    prepared = adapter.prepare(context)
    raw = adapter.predict(prepared, context)
    result = validate_model_result(adapter.normalize_result(raw, context), spec)
    atomic_json(job_dir / 'model-result.json', result.to_dict())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', choices=('prepare', 'model'), required=True)
    parser.add_argument('--job-dir', type=Path, required=True)
    args = parser.parse_args()
    {'prepare': prepare, 'model': model}[args.task](args.job_dir.resolve())


if __name__ == '__main__': main()

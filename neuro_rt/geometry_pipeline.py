"""Explicit physical-space preparation/restoration in the worker runtime.

SimpleITK reads NIfTI RAS headers into LPS physical coordinates. No array flip
or header replacement implements a registration here. Published network-specific
crop/normalization/reconstruction remains the adapter backend's responsibility.
"""
from .scientific_io import read_image, write_image, read_transform
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from .adapters.base import GeometryReport, PreparedInputs
from .study_types import MaskArtifact, SeriesDescriptor


def _image(value):
    import SimpleITK as sitk
    return read_image(str(value)) if isinstance(value, (str, Path)) else value


def verify_reference_geometry(mask, reference) -> GeometryReport:
    """Compare complete physical grids (millimetres, LPS), never shape alone."""
    import numpy as np
    from .imaging import geometry
    actual = geometry(_image(mask))
    expected = (reference.geometry if isinstance(reference, SeriesDescriptor)
                else reference if isinstance(reference, dict) else geometry(_image(reference)))
    errors = []
    for key, length in (('size_xyz', 3), ('spacing_xyz_mm', 3),
                        ('origin_lps_mm', 3), ('direction_lps', 9)):
        wanted, found = expected.get(key, []), actual.get(key, [])
        if (len(wanted) != length or len(found) != length or
                not np.isfinite(wanted).all() or not np.isfinite(found).all() or
                not np.allclose(wanted, found, atol=0 if key == 'size_xyz' else 1e-4, rtol=0)):
            errors.append(key)
    return GeometryReport(not errors, dict(expected), actual, errors)


def _digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_transform(transform, dimension, _depth=0):
    """Reject invalid components, including non-optimized composite members."""
    import numpy as np
    import SimpleITK as sitk
    if (_depth > 32 or transform.GetDimension() != dimension or
            not np.isfinite(transform.GetParameters()).all() or
            not np.isfinite(transform.GetFixedParameters()).all()):
        raise ValueError('A transformação exige dimensão correta e parâmetros finitos.')
    if transform.GetName() == 'CompositeTransform':
        composite = sitk.CompositeTransform(transform)
        for index in range(composite.GetNumberOfTransforms()):
            _validate_transform(composite.GetNthTransform(index), dimension, _depth + 1)
    elif transform.GetTransformEnum() == sitk.sitkComposite:
        raise ValueError('Transformação genérica composta não pode ser verificada.')


def _inverse_transform(transform, dimension):
    """Invert validated members separately: ITK composite inversion can return
    MatrixOffsetTransformBase members that SITK downcasts into self-wrappers.
    Member-wise inversion preserves the exact physical composition order.
    """
    import SimpleITK as sitk
    _validate_transform(transform, dimension)
    if transform.GetName() == 'CompositeTransform':
        composite = sitk.CompositeTransform(transform)
        inverse = sitk.CompositeTransform(dimension)
        for index in reversed(range(composite.GetNumberOfTransforms())):
            inverse.AddTransform(_inverse_transform(composite.GetNthTransform(index), dimension))
    else:
        inverse = transform.GetInverse()
    _validate_transform(inverse, dimension)
    return inverse


def _registration_inverse(path, dimension):
    import SimpleITK as sitk
    try:
        transform = read_transform(str(path))
        _validate_transform(transform, dimension)
        inverse = _inverse_transform(transform, dimension)
        _validate_transform(inverse, dimension)
    except RuntimeError as exc:
        raise ValueError('A transformação de registro não pode ser lida ou invertida.') from exc
    return inverse


def prepare_model_inputs(bindings, reference, model_spec, context) -> PreparedInputs:
    """Order authorized channels and explicitly register them onto the reference.

    A distinct ticket requires a supplied source->reference transform even when
    headers match. Linear interpolation is used only for scalar input intensities.
    No estimated registration or normalization is silently applied.
    """
    import SimpleITK as sitk
    from .imaging import check_volume, geometry
    context.checkpoint('preparing', 0.)
    roles = [entry['role'] for entry in model_spec['channels']]
    by_role = {binding.role: binding for binding in bindings}
    if not roles or len(set(roles)) != len(roles) or len(by_role) != len(bindings) or set(by_role) != set(roles):
        raise ValueError('Canais ausentes, repetidos ou inesperados.')
    tickets = [by_role[role].series_ticket for role in roles]
    if len(set(tickets)) != len(tickets):
        raise ValueError('Uma série repetida não pode preencher dois canais.')
    for ticket in [reference.ticket, *tickets]:
        if ticket not in context.authorized_inputs or ticket not in context.series_index:
            raise ValueError('Entrada não pertence ao inventário autorizado.')
    ref_path = Path(context.authorized_inputs[reference.ticket]).resolve()
    ref_image = read_image(str(ref_path))
    check_volume(ref_image)
    if not verify_reference_geometry(ref_image, reference).valid:
        raise ValueError('Geometria real da referência diverge do descritor autorizado.')
    directory = Path(context.job_dir).resolve() / 'prepared'
    channels, chain, identities, loaded = [], [], [], []
    for role, ticket in zip(roles, tickets):
        context.checkpoint('preparing', 0.)
        descriptor = context.series_index[ticket]
        if (descriptor.subject_key != reference.subject_key or descriptor.study_key != reference.study_key
                or descriptor.modality != reference.modality):
            raise ValueError('Séries não pertencem ao mesmo sujeito, estudo e modalidade.')
        path = Path(context.authorized_inputs[ticket]).resolve()
        image = read_image(str(path))
        check_volume(image)
        if not verify_reference_geometry(image, descriptor).valid:
            raise ValueError('Geometria da entrada diverge do descritor autorizado.')
        transform_path = context.source_to_reference.get(ticket)
        step = {'role': role, 'source_ticket': ticket, 'target_ticket': reference.ticket,
                'coordinate_system': 'LPS', 'source_geometry': geometry(image),
                'target_geometry': geometry(ref_image)}
        if ticket != reference.ticket:
            if transform_path is None:
                raise ValueError('Uma série diferente exige registro explícito para a referência.')
            transform_path = Path(transform_path).resolve()
            # Resample requires reference->source, the inverse of our contract.
            ref_to_source = _registration_inverse(transform_path, ref_image.GetDimension())
            image = sitk.Resample(image, ref_image, ref_to_source, sitk.sitkLinear,
                                 0., sitk.sitkFloat32)
            step.update(operation='registration_resample', transform_path=str(transform_path),
                        transform_sha256=_digest(transform_path), direction='source_to_reference',
                        interpolation='linear')
        else:
            step.update(operation='identity', interpolation='none')
        identities.append({'role': role, 'ticket': ticket, 'sha256': _digest(path)})
        loaded.append(image)
        chain.append(step)
    directory.mkdir(parents=True, exist_ok=True)
    for index, image in enumerate(loaded):
        destination = directory / f'input{index}.nii.gz'
        write_image(image, str(destination))
        channels.append(str(destination))
    cache_key = hashlib.sha256(json.dumps({'inputs': identities, 'model': model_spec,
                                          'chain': chain}, sort_keys=True).encode()).hexdigest()
    context.checkpoint('preparing', 1.)
    return PreparedInputs(channels, roles, geometry(ref_image), reference, chain, cache_key,
                          str(ref_path), str(Path(context.job_dir).resolve() / 'restored'))


def restore_masks(model_result, prepared, reference) -> list[MaskArtifact]:
    """Restore binary class masks independently with nearest-neighbour sampling.

    ``working`` means physical LPS coordinates of the prepared reference; a
    cropped/resampled image must carry its true physical header. ``reference``
    promises the exact original grid and is verified without repairing its header.
    Probability thresholding and inverse network transforms belong to the backend.
    """
    import numpy as np
    import SimpleITK as sitk
    from .imaging import check_volume, geometry
    if reference != prepared.reference:
        raise ValueError('Referência diferente daquela usada na preparação.')
    ref_image = read_image(prepared.reference_path)
    if not verify_reference_geometry(ref_image, reference).valid:
        raise ValueError('Referência alterada após a preparação.')
    output_dir = Path(prepared.output_dir)
    artifacts, seen = [], set()
    for index, mask in enumerate(model_result.masks):
        identity = (type(mask.class_id), mask.class_id)
        if mask.model_id != model_result.model_id or identity in seen:
            raise ValueError('Identidade de modelo/classe inconsistente ou repetida.')
        seen.add(identity)
        image = read_image(mask.path)
        check_volume(image)
        if not verify_reference_geometry(image, mask.geometry).valid:
            raise ValueError('Geometria da máscara diverge da declaração do motor.')
        if not np.isin(sitk.GetArrayViewFromImage(image), [0, 1]).all():
            raise ValueError('O retorno exige máscara binária, sem limiar implícito.')
        if mask.space == 'reference':
            if not verify_reference_geometry(image, reference).valid:
                raise ValueError('Máscara declarada na referência está fora de sua geometria.')
        elif mask.space == 'working':
            image = sitk.Resample(image, ref_image, sitk.Transform(3, sitk.sitkIdentity),
                                 sitk.sitkNearestNeighbor, 0, sitk.sitkUInt8)
        else:
            raise ValueError('Espaço de máscara sem transformação de retorno declarada.')
        if not verify_reference_geometry(image, reference).valid:
            raise ValueError('Restauração não alcançou a geometria física de referência.')
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / f'class_{index}.nii.gz'
        write_image(sitk.Cast(image, sitk.sitkUInt8), str(destination))
        artifacts.append(replace(mask, path=str(destination), geometry=geometry(image),
                                 space='reference', provenance={**mask.provenance,
                                 'restoration': 'physical_lps_nearest_neighbor',
                                 'reference_ticket': reference.ticket,
                                 'prepared_cache_key': prepared.cache_key}))
    return artifacts

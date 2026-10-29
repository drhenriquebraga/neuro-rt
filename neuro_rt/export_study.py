"""One RTSTRUCT per v2 study reference, using the existing Local Suite writer.

Run this module in the host Python subprocess, never in the HTTP/queue process.
The private source sidecar is server-written and is not accepted from UI JSON.
"""
from .scientific_io import read_image
import argparse
from dataclasses import replace
import json
from pathlib import Path
import shutil
import sys
import uuid

from .export import verify_rtstruct
from .result_store import atomic_json, validate_manifest
from .roi_registry import collect_reference_masks
from .study_types import ExportReceipt


class IncompleteExport(ValueError):
    """Masks remain valid/private, but the writer could not retain every ROI."""


def _geometry_equal(first, second):
    import numpy as np
    return set(first) == set(second) and all(
        np.allclose(first[key], second[key], atol=1e-4, rtol=0) for key in first)


def _mask_path(job, path):
    raw = Path(path)
    if not raw.is_absolute() and ('..' in raw.parts or ':' in path or '\\' in path):
        raise ValueError('Caminho privado de máscara inválido.')
    target = raw.resolve() if raw.is_absolute() else (job / raw).resolve()
    if not target.is_relative_to(job) or target.relative_to(job).parts[0] not in ('masks', 'models'):
        raise ValueError('Máscara fora da pasta privada de resultados.')
    return target


def _check_source(source, reference, image, expected_geometry):
    from .imaging import geometry
    if (source.get('kind') != 'dicom' or source.get('series_uid') != reference.series_uid or
            (source.get('modality') and source['modality'] != reference.modality) or
            source.get('frame_uid') != reference.frame_of_reference_uid or
            set(source.get('sop_uids', [])) != set(reference.sop_instance_uids) or
            not _geometry_equal(geometry(image), expected_geometry)):
        raise ValueError('A referência DICOM não corresponde ao manifesto.')


def _check_written(path, source, expected, source_dir):
    """Validate metadata and exact voxel round trip, including tiny secondary foci."""
    import numpy as np
    import pydicom
    from rt_utils import RTStructBuilder
    from radai_rt import SessaoRT
    verify_rtstruct(path, source)
    ds = pydicom.dcmread(str(path))
    names = [str(roi.ROIName) for roi in ds.StructureSetROISequence]
    delivered, omitted = sorted(set(names) & set(expected)), sorted(set(expected) - set(names))
    if len(names) != len(set(names)) or set(names) - set(expected):
        raise IncompleteExport('O gravador alterou a identidade das ROIs solicitadas.')
    if omitted:
        return ds, delivered, omitted
    rt = RTStructBuilder.create_from(dicom_series_path=str(source_dir), rt_struct_path=str(path))
    # The host writes boundaries at half-pixels. rt_utils rounds those vertices
    # before fillPoly and can add a full rim of voxels. Reuse the host's reader,
    # which rasterizes at voxel centres, then retain exact array equality below.
    reader = SessaoRT(None, str(path), None, next(iter(expected.values())).shape, names, rt)
    numbers = {int(roi.ROINumber): str(roi.ROIName) for roi in ds.StructureSetROISequence}
    observations = ds.get('RTROIObservationsSequence', [])
    if {int(item.ReferencedROINumber) for item in observations} != set(numbers):
        raise IncompleteExport('O gravador não conservou a procedência de todas as ROIs.')
    for item in observations:
        description = str(item.get('ROIObservationDescription', ''))
        if 'NeuroRT / modelo ' not in description or '/ classe ' not in description:
            raise IncompleteExport('O gravador não conservou a identidade de modelo/classe.')
    planes = {}
    for file in source['dicom_files']:
        header = pydicom.dcmread(str(file), stop_before_pixels=True,
            specific_tags=['SOPInstanceUID', 'ImageOrientationPatient', 'ImagePositionPatient'])
        orientation = np.asarray(header.ImageOrientationPatient, dtype=float)
        planes[str(header.SOPInstanceUID)] = (np.asarray(header.ImagePositionPatient, dtype=float),
                                              np.cross(orientation[:3], orientation[3:]))
    for contour in ds.get('ROIContourSequence', []):
        name = numbers[int(contour.ReferencedROINumber)]
        sequences = contour.get('ContourSequence', [])
        if not sequences or any(int(c.NumberOfContourPoints) < 3 or
                str(c.ContourGeometricType) != 'CLOSED_PLANAR' or
                len(c.get('ContourImageSequence', [])) != 1 or
                any(str(item.ReferencedSOPInstanceUID) not in source['sop_uids']
                    for item in c.get('ContourImageSequence', [])) for c in sequences):
            omitted.append(name)
        for sequence in sequences:
            refs = sequence.get('ContourImageSequence', [])
            if len(refs) != 1 or str(refs[0].ReferencedSOPInstanceUID) not in planes:
                continue
            origin, normal = planes[str(refs[0].ReferencedSOPInstanceUID)]
            points = np.asarray(sequence.ContourData, dtype=float).reshape(-1, 3)
            if (not np.isfinite(points).all() or
                    not np.allclose((points-origin) @ normal, 0., atol=1e-3, rtol=0)):
                omitted.append(name)
    for name, bits in expected.items():
        if name in omitted:
            continue
        restored = reader.mascara(name)
        if restored.shape != bits.shape or not np.array_equal(restored, bits):
            omitted.append(name)
    omitted = sorted(set(omitted))
    return ds, sorted(set(delivered) - set(omitted)), omitted


def export_study(job_dir, host_app, *, catalog=None):
    """Return an ExportReceipt, or None for empty masks; update private manifest.

    Incomplete/failed publication raises after atomically recording its status.
    Valid masks and an internal DICOM copy survive for retry/inspection.
    """
    job = Path(job_dir).resolve()
    manifest_path = job / 'study-manifest.json'
    manifest = validate_manifest(json.loads(manifest_path.read_text(encoding='utf-8')), catalog)
    source = None
    receipt = None
    incomplete = False

    def persist(status, receipt):
        updated = replace(manifest, export_status=status, export_receipt=receipt)
        atomic_json(manifest_path, updated.to_dict())

    try:
        if (manifest.reference.source_format != 'dicom' or
                manifest.status not in ('completed', 'partial', 'empty', 'exporting')):
            raise ValueError('Resultado não permite exportação DICOM-RT.')
        from integration.host_imports import prepare_host_imports
        prepare_host_imports(host_app)
        import engine
        import numpy as np
        import SimpleITK as sitk
        from .imaging import geometry, load_input, validate_mask, dicom_series

        reference_image = read_image(str(job / 'inputs/reference.nii.gz'))
        if not _geometry_equal(geometry(reference_image), manifest.reference.geometry):
            raise ValueError('A imagem de referência mudou após a inferência.')
        masks, descriptions, identities, expected = {}, {}, {}, {}
        for identity, artifact in collect_reference_masks(manifest, catalog=catalog):
            image = read_image(str(_mask_path(job, artifact.path)))
            metrics = validate_mask(image, reference_image)
            if artifact.geometry and not _geometry_equal(geometry(image), artifact.geometry):
                raise ValueError('Geometria privada da máscara diverge de seu manifesto.')
            if not metrics['voxels']:
                continue
            bits = np.array(sitk.GetArrayFromImage(image), dtype=bool)
            masks[identity.writer_key] = bits
            expected[identity.roi_name] = bits
            descriptions[identity.writer_key] = identity.description
            identities[identity.roi_name] = identity
        if not masks:
            persist('empty', None)
            return None

        source = json.loads((job / 'source.json').read_text(encoding='utf-8'))
        if not isinstance(source, dict) or source.get('kind') != 'dicom':
            raise ValueError('Origem DICOM privada ausente.')
        source_dir = job / 'dicom_source'
        series = dicom_series(source_dir, allowed_modalities=(manifest.reference.modality,))
        if len(series) != 1 or series[0]['uid'] != manifest.reference.series_uid:
            raise ValueError('A cópia privada deve conter somente a referência.')
        image, copied_source = load_input(source_dir, manifest.reference.series_uid,
                                         allowed_modalities=(manifest.reference.modality,))
        _check_source(copied_source, manifest.reference, image, geometry(reference_image))
        _check_source(source, manifest.reference, image, geometry(reference_image))
        if not source.get('input_path') or not source.get('dicom_files'):
            raise ValueError('Origem original privada incompleta.')
        original = Path(source['input_path']).resolve()

        def verify_original():
            original_image, original_source = load_input(original, manifest.reference.series_uid,
                allowed_modalities=(manifest.reference.modality,))
            _check_source(original_source, manifest.reference, original_image, geometry(reference_image))
            if {str(Path(f).resolve()) for f in original_source['dicom_files']} != {
                    str(Path(f).resolve()) for f in source['dicom_files']}:
                raise ValueError('Arquivos DICOM originais foram substituídos.')
        verify_original()
        path, _ = engine.build_rtstruct(str(source_dir), masks, cru=True,
                    descontar=False, suavizar_mm=0., modalidade=manifest.reference.modality,
                    rotulo='RadAI_NEURO', origem={key: 'neuro-rt' for key in masks},
                    observacoes=descriptions, decimar_mm=0.)
        exports = job / 'exports'
        exports.mkdir(exist_ok=True)
        filename = f'RS_NeuroRT_{uuid.uuid4().hex}.dcm'
        internal = exports / filename
        shutil.copyfile(path, internal)
        # The host remains the sole contour writer. Match its presentation
        # metadata to the same model/class palette used by NeuroRT's viewers.
        import pydicom
        colored = pydicom.dcmread(str(internal))
        names_by_number = {int(roi.ROINumber): str(roi.ROIName)
                           for roi in colored.get('StructureSetROISequence', [])}
        for roi in colored.get('ROIContourSequence', []):
            name = names_by_number.get(int(roi.ReferencedROINumber))
            if name in identities:
                roi.ROIDisplayColor = list(identities[name].color)
        # The host already emitted Part 10. Preserve its file metadata/encoding;
        # enforcing a new format would add pydicom's implementation-version tag.
        colored.save_as(str(internal))
        ds, delivered, omitted = _check_written(internal, source, expected, source_dir)
        receipt = ExportReceipt('', str(ds.SOPInstanceUID), manifest.reference.ticket,
                                delivered, omitted, manifest.revision)
        if omitted:
            incomplete = True
            persist('incomplete', receipt)
            raise IncompleteExport('O gravador não preservou todas as ROIs e seus focos; máscaras conservadas.')
        # Repeat immediately before exclusive publication; never publish the cache as source.
        verify_original()
        destination = original / filename
        temporary_publication = destination.with_suffix('.part')
        created = False
        try:
            with temporary_publication.open('xb') as output:
                created = True
                with internal.open('rb') as input_file:
                    shutil.copyfileobj(input_file, output)
                    output.flush()
                    import os
                    os.fsync(output.fileno())
            verify_original()
            if os.name == 'nt':
                # Windows rename is atomic and refuses an existing destination.
                os.rename(temporary_publication, destination)
            else:
                # POSIX rename can replace; an exclusive link avoids that.
                os.link(temporary_publication, destination)
                temporary_publication.unlink()
        except Exception:
            # A partially copied file must never look like a complete published result.
            if created:
                temporary_publication.unlink(missing_ok=True)
            raise
        receipt = replace(receipt, published_file=str(destination))
        # Unique internal artifact names preserve older retries and their downloads.
        artifacts = list(manifest.artifacts) + [{
            'artifact_id': 'a' + uuid.uuid4().hex, 'kind': 'rtstruct',
            'media_type': 'application/dicom', 'path': str(internal)}]
        manifest = replace(manifest, artifacts=artifacts)
        persist('completed', receipt)
        return receipt
    except Exception:
        if not incomplete:
            persist('failed', replace(receipt, published_file='') if receipt else None)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job-dir', required=True, type=Path)
    parser.add_argument('--host-app', required=True, type=Path)
    args = parser.parse_args()
    try:
        export_study(args.job_dir, args.host_app)
    except Exception:
        # Scientific/writer traces remain local to the caller's private subprocess log.
        import traceback
        traceback.print_exc()
        print('Exportação não concluída; consulte o registro privado da execução.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

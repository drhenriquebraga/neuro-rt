"""Adaptador para o gravador do host, executado pelo Python do Local Suite."""
import argparse
from contextlib import contextmanager
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

MASK_HEAP_BUDGET = 64 * 1024**2


@contextmanager
def temporary_writer_result(result):
    import engine
    path = Path(result[0])
    resolved = path.resolve()
    try:
        yield resolved, result[1]
    finally:
        # Only the RS.dcm created by this call to build_rtstruct belongs to
        # the exporter. Never recursively delete a job, input or arbitrary path.
        folder = resolved.parent
        if (path.absolute() == resolved and resolved.name == 'RS.dcm' and
                folder.parent == Path(tempfile.gettempdir()).resolve() and
                folder.name.startswith(engine.PREFIXO_TEMP_DO_RS)):
            resolved.unlink(missing_ok=True)
            try:
                folder.rmdir()
            except OSError:
                pass


def verify_rtstruct(path, source, dataset=None):
    import pydicom
    ds = dataset if dataset is not None else pydicom.dcmread(str(path))
    if str(ds.get('Modality', '')) != 'RTSTRUCT' or str(ds.get('ApprovalStatus', '')) != 'UNAPPROVED':
        raise ValueError('O gravador não produziu RTSTRUCT UNAPPROVED.')
    frames = ds.get('ReferencedFrameOfReferenceSequence', [])
    if len(frames) != 1 or str(frames[0].FrameOfReferenceUID) != source['frame_uid']:
        raise ValueError('Frame of Reference diferente da RM original.')
    series = frames[0].RTReferencedStudySequence[0].RTReferencedSeriesSequence
    if len(series) != 1 or str(series[0].SeriesInstanceUID) != source['series_uid']:
        raise ValueError('RTSTRUCT referencia outra série.')
    referenced = {str(item.ReferencedSOPInstanceUID) for item in series[0].ContourImageSequence}
    if referenced != set(source['sop_uids']):
        raise ValueError('Referências de imagens não correspondem à série original.')
    names = [str(item.ROIName) for item in ds.get('StructureSetROISequence', [])]
    if not names or any(not name.endswith('_ai') for name in names):
        raise ValueError('ROI sem procedência ou RTSTRUCT sem estruturas.')
    for roi in ds.StructureSetROISequence:
        if str(roi.ReferencedFrameOfReferenceUID) != source['frame_uid']:
            raise ValueError('ROI vinculada a outro Frame of Reference.')
    for item in ds.get('RTROIObservationsSequence', []):
        if str(item.get('RTROIInterpretedType', '')) == 'EXTERNAL':
            raise ValueError('O módulo de lesão não pode declarar contorno externo.')
        if 'NeuroRT' not in str(item.get('ROIObservationDescription', '')):
            raise ValueError('Descrição da ROI sem procedência NeuroRT.')
    return {'approval_status': 'UNAPPROVED', 'frame_uid': source['frame_uid'], 'roi_names': names}


def source_planes(source):
    import pydicom
    from radai_rt import PlanoDaImagem
    result = {}
    for z, file in enumerate(source['dicom_files']):
        image = pydicom.dcmread(str(file), stop_before_pixels=True, specific_tags=[
            'SOPInstanceUID', 'SOPClassUID', 'ImageOrientationPatient',
            'ImagePositionPatient', 'PixelSpacing', 'Rows', 'Columns'])
        uid = str(image.SOPInstanceUID)
        if uid != source['sop_uids'][z] or uid in result:
            raise ValueError('A ordem das imagens não corresponde à referência da máscara.')
        result[uid] = (z, PlanoDaImagem(image), str(image.SOPClassUID),
                       (int(image.Rows), int(image.Columns)))
    return result


def mask_matches_contours(roi, mask, planes):
    """Verify physical coordinates, source image and parity on one slice at a time."""
    import numpy as np
    from radai_rt import centros_no_poligono
    shape = mask.shape
    if len(planes) != shape[0]:
        return False
    by_image = {}
    for contour in roi.get('ContourSequence', []):
        refs = contour.get('ContourImageSequence', [])
        if len(refs) != 1 or str(contour.ContourGeometricType) != 'CLOSED_PLANAR':
            return False
        uid = str(refs[0].ReferencedSOPInstanceUID)
        if uid not in planes or str(refs[0].ReferencedSOPClassUID) != planes[uid][2]:
            return False
        by_image.setdefault(uid, []).append(contour)
    for uid, (z, plane, _, dimensions) in planes.items():
        if dimensions != shape[1:]:
            return False
        expected = mask[z]
        if uid not in by_image:
            if expected.any():
                return False
            continue
        actual = np.zeros(dimensions, dtype=bool)
        for contour in by_image[uid]:
            # Leave the original encoded DS in the dataset. A large atlas
            # must not retain millions of Python objects during verification.
            element = contour.get_item(0x30060050)
            if element is None:
                return False
            if getattr(element, 'is_raw', False) and isinstance(element.value, bytes):
                points = np.fromstring(element.value.rstrip(b' \0'), dtype=float, sep='\\')
            else:
                points = np.asarray(contour.ContourData, dtype=float)
            n = int(contour.NumberOfContourPoints)
            if n < 3 or points.size != 3*n or not np.isfinite(points).all():
                return False
            points = points.reshape(-1, 3)
            pixels = plane.pixels(points)
            if not np.allclose(plane.paciente(pixels), points, atol=1e-3, rtol=0):
                return False
            x0, y0 = np.maximum([0, 0], np.floor(pixels.min(axis=0)).astype(int))
            x1, y1 = np.minimum(np.array(dimensions[::-1])-1, np.ceil(pixels.max(axis=0)).astype(int))
            if x0 <= x1 and y0 <= y1:
                # CLOSED_PLANAR stores each hole as a keyhole. Separate
                # contours on the same image are solid, disconnected regions.
                actual[y0:y1+1, x0:x1+1] |= centros_no_poligono(pixels, x0, x1, y0, y1)
        if not np.array_equal(actual, expected):
            return False
    return True


def export(job_dir, host_app):
    job_dir, host_app = Path(job_dir).resolve(), Path(host_app).resolve()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from integration.host_imports import prepare_host_imports
    prepare_host_imports(host_app)
    import SimpleITK as sitk
    import engine
    from neuro_rt.imaging import load_input, validate_mask, geometry

    manifest_path = job_dir / 'manifest.json'
    result = json.loads(manifest_path.read_text(encoding='utf-8'))
    if (result.get('schema') != 'neuro-rt/result/1' or
        result.get('approval_status') != 'UNAPPROVED' or result.get('status') != 'completed' or
        result.get('source', {}).get('kind') != 'dicom'):
        raise ValueError('Resultado não permite exportação para DICOM-RT.')
    source_dir = job_dir / 'dicom_source'
    image, source = load_input(source_dir, result['source']['series_uid'])
    if source['frame_uid'] != result['source']['frame_uid'] or geometry(image) != result['geometry']:
        raise ValueError('Série de origem não corresponde ao manifesto.')
    if not result['source'].get('input_path'):
        raise ValueError('Pasta original ausente no manifesto.')
    original = Path(result['source']['input_path']).resolve()
    if not original.is_dir():
        raise ValueError('Pasta original da série não está disponível para gravar RTSTRUCT.')
    original_image, original_source = load_input(original, source['series_uid'])
    if (original_source['frame_uid'] != source['frame_uid'] or
        set(original_source['sop_uids']) != set(source['sop_uids']) or
        geometry(original_image) != geometry(image)):
        raise ValueError('A série original mudou; o RTSTRUCT não será publicado.')
    masks, notes = {}, {}
    for item in result['masks']:
        file = (job_dir / item['path']).resolve()
        if not file.is_relative_to(job_dir / 'masks'):
            raise ValueError('Máscara fora da pasta de resultados.')
        mask = sitk.ReadImage(str(file))
        metrics = validate_mask(mask, image)
        if not metrics['voxels']:
            continue
        name = item['roi_name']
        if name != 'Tumor_NeuroRT':
            raise ValueError('Nome de ROI fora do contrato deste módulo.')
        masks[name] = engine.MascaraCompacta.de(sitk.GetArrayViewFromImage(mask), MASK_HEAP_BUDGET)
        notes[name] = (f"Sugestao nao aprovada. NeuroRT / modelo {result['model_id']} / pesos {result['model_release']}. "
                       'Mascara na RM original; sem CTV automatico ou registro RM-TC.')
    if not masks:
        raise ValueError('Não há máscara não vazia para exportar.')
    built = engine.build_rtstruct(str(source_dir), masks, cru=True, descontar=False,
                                       suavizar_mm=0., modalidade='MR', rotulo='RadAI_NEURO',
                                       origem={name: 'neuro-rt' for name in masks}, observacoes=notes,
                                       contornos_subpixel=True)
    with temporary_writer_result(built) as (path, names):
        import pydicom
        ds = pydicom.dcmread(path)
        checked = verify_rtstruct(path, source, dataset=ds)
        numbers = {int(r.ROINumber): str(r.ROIName) for r in ds.StructureSetROISequence}
        expected = {names[key]: value for key, value in masks.items()}
        planes = source_planes(source)
        if (set(checked['roi_names']) != set(expected) or
                {int(r.ReferencedROINumber) for r in ds.ROIContourSequence} != set(numbers) or
                len(ds.ROIContourSequence) != len(expected) or
                any(not mask_matches_contours(r, expected[numbers[int(r.ReferencedROINumber)]], planes)
                    for r in ds.ROIContourSequence)):
            raise ValueError('Os contornos não correspondem às máscaras neuro na grade original.')
        filename = f'RS_NeuroRT_{uuid.uuid4().hex[:12]}.dcm'
        destination = original / filename
        staging = destination.with_suffix('.part')
        with staging.open('xb') as out:
            try:
                with path.open('rb') as infile:
                    shutil.copyfileobj(infile, out)
                out.flush()
                os.fsync(out.fileno())
            except Exception:
                out.close()
                staging.unlink(missing_ok=True)
                raise
        try:
            if os.name == 'nt':
                os.rename(staging, destination)
            else:
                os.link(staging, destination)
        finally:
            staging.unlink(missing_ok=True)
        shutil.copyfile(destination, job_dir/'RS_NeuroRT.dcm')
    result['rtstruct'] = {'path': 'RS_NeuroRT.dcm', 'source_path':str(destination), **checked}
    manifest_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('RTSTRUCT gravado pelo Local Suite e referências DICOM conferidas.', flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job-dir', type=Path, required=True)
    parser.add_argument('--host-app', type=Path, required=True)
    args = parser.parse_args()
    export(args.job_dir, args.host_app)


if __name__ == '__main__':
    main()

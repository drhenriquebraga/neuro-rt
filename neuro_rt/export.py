"""Adaptador para o gravador do host, executado pelo Python do Local Suite."""
import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path


def verify_rtstruct(path, source):
    import pydicom
    ds = pydicom.dcmread(str(path))
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


def export(job_dir, host_app):
    job_dir, host_app = Path(job_dir).resolve(), Path(host_app).resolve()
    sys.path.insert(0, str(host_app))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import numpy as np
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
        masks[name] = np.array(sitk.GetArrayFromImage(mask), dtype=bool)
        notes[name] = (f"Sugestao nao aprovada. NeuroRT / modelo {result['model_id']} / pesos {result['model_release']}. "
                       'Mascara na RM original; sem CTV automatico ou registro RM-TC.')
    if not masks:
        raise ValueError('Não há máscara não vazia para exportar.')
    path, names = engine.build_rtstruct(str(source_dir), masks, cru=True, descontar=False,
                                       suavizar_mm=0., modalidade='MR', rotulo='RadAI_NEURO',
                                       origem={name: 'neuro-rt' for name in masks}, observacoes=notes)
    checked = verify_rtstruct(path, source)
    if len(checked['roi_names']) != len(masks):
        raise ValueError('O gravador descartou uma ROI; resultado não será entregue como completo.')
    filename = f'RS_NeuroRT_{uuid.uuid4().hex[:12]}.dcm'
    destination = original / filename
    with destination.open('xb') as out, Path(path).open('rb') as input_file:
        shutil.copyfileobj(input_file,out)
    shutil.copyfile(destination,job_dir/'RS_NeuroRT.dcm')
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

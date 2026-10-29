"""Inferência isolada. Somente arquivos locais; nenhum download neste caminho."""
import argparse
import configparser
import importlib.metadata
import json
import shutil
from pathlib import Path

from .catalog import get_model, validate_model_folder, requires_brain, BRAIN, RELEASE, MODEL_LOCK
from .contracts import validate_request
from .imaging import geometry, load_input, validate_mask


def write_runtime_config(job_dir, model_folder, device, output_name='predictions', brain_mask=None):
    job_dir = Path(job_dir).resolve()
    model_folder = Path(model_folder).resolve()
    if any(char in str(path) for path in (job_dir, model_folder) for char in '#%'):
        raise ValueError('O backend não aceita # ou % nos caminhos de trabalho/modelo.')
    cfg = configparser.ConfigParser(interpolation=None)
    cfg['System'] = {'gpu_id': '0' if device == 'cuda' else '-1', 'acceleration': 'cpu',
                     'inputs_folder': str(job_dir / 'inputs'),
                     'output_folder': str(job_dir / output_name), 'model_folder': str(model_folder)}
    cfg['Runtime'] = {'batch_size': '1', 'folds_ensembling': 'false',
                      'reconstruction_method': 'thresholding', 'reconstruction_order': 'resample_first',
                      'use_preprocessed_data': 'false', 'test_time_augmentation_iteration': '0'}
    if brain_mask:
        cfg['Neuro'] = {'brain_segmentation_filename': str(brain_mask)}
    path = job_dir / f'{output_name}.ini'
    with path.open('w', encoding='utf-8') as handle:
        cfg.write(handle)
    return path


def run_job(request, job_dir, models_dir):
    import SimpleITK as sitk
    import onnxruntime as ort
    from raidionicsseg.fit import run_model

    request = validate_request(request)
    model = get_model(request['model'])
    folder = Path(models_dir).resolve() / model['id']
    classes = validate_model_folder(folder, model)
    if request['device'] == 'auto':
        request['device'] = 'cpu'
        if 'CUDAExecutionProvider' in ort.get_available_providers():
            try:
                candidate = ort.InferenceSession(str(folder / 'fold0/model.onnx'), providers=['CUDAExecutionProvider'])
                if 'CUDAExecutionProvider' in candidate.get_providers():
                    request['device'] = 'cuda'
                del candidate
            except Exception:
                pass
    if request['device'] == 'cuda' and 'CUDAExecutionProvider' not in ort.get_available_providers():
        raise ValueError('CUDA indisponível neste ambiente; escolha CPU ou prepare onnxruntime-gpu.')
    if request['device'] == 'cuda':
        session = ort.InferenceSession(str(folder / 'fold0/model.onnx'), providers=['CUDAExecutionProvider'])
        if 'CUDAExecutionProvider' not in session.get_providers():
            raise ValueError('CUDA não inicializou; inferência não será executada com fallback silencioso.')
        del session
    job_dir = Path(job_dir).resolve()
    inputs = job_dir / 'inputs'
    inputs.mkdir(parents=True, exist_ok=False)
    (job_dir / 'predictions').mkdir()
    print('Lendo e conferindo a geometria da RM.', flush=True)
    image, source = load_input(request['input_path'], request['series_uid'])
    sitk.WriteImage(image, str(inputs / 'input0.nii.gz'))
    if source['dicom_files']:
        stage = job_dir / 'dicom_source'
        stage.mkdir()
        for i, file in enumerate(source['dicom_files']):
            shutil.copyfile(file, stage / f'{i:06d}.dcm')
    brain_mask = None
    if requires_brain(folder):
        brain_folder = Path(models_dir).resolve() / BRAIN['id']
        validate_model_folder(brain_folder, BRAIN)
        (job_dir / 'brain_predictions').mkdir()
        print('Gerando máscara cerebral auxiliar oficial.', flush=True)
        brain_cfg = write_runtime_config(job_dir, brain_folder, request['device'], 'brain_predictions')
        run_model(config_filename=str(brain_cfg))
        brain_mask = job_dir / 'brain_predictions' / 'labels_Brain.nii.gz'
        if not brain_mask.is_file():
            raise RuntimeError('O modelo auxiliar não produziu a máscara cerebral esperada.')
        if not validate_mask(sitk.ReadImage(str(brain_mask)), image)['voxels']:
            raise ValueError('Máscara cerebral vazia; a inferência tumoral não será executada.')
    cfg = write_runtime_config(job_dir, folder, request['device'], brain_mask=brain_mask)
    print(f"ACHADO solicitado: {model['id']}; inferência {request['device']} com pesos locais.", flush=True)
    run_model(config_filename=str(cfg))
    masks_dir = job_dir / 'masks'
    masks_dir.mkdir()
    masks = []
    for label in classes:
        # Nome produzido pelo backend oficial; nunca selecionar o primeiro NIfTI da pasta.
        candidates = list((job_dir / 'predictions').glob(f'*_{label}.nii.gz'))
        if len(candidates) != 1:
            raise RuntimeError(f'Esperada exatamente uma máscara de {label}; encontradas {len(candidates)}.')
        output = sitk.ReadImage(str(candidates[0]))
        metrics = validate_mask(output, image)
        destination = masks_dir / f'{label}.nii.gz'
        sitk.WriteImage(sitk.Cast(output, sitk.sitkUInt8), str(destination))
        masks.append({'label': label, 'roi_name': 'Tumor_NeuroRT',
                      'path': destination.relative_to(job_dir).as_posix(), **metrics})
    from neuro_rt import __version__
    result = {'schema': 'neuro-rt/result/1', 'module_version': __version__,
              'model_id': model['id'], 'model_release': RELEASE,
              'model_sha256': MODEL_LOCK[model['id']]['files']['fold0/model.onnx'],
              'required_sequence': model['sequence'], 'brain_model_id': BRAIN['id'] if brain_mask else None,
              'backend_version': importlib.metadata.version('raidionicsseg'),
              'approval_status': 'UNAPPROVED', 'geometry': geometry(image),
              'source': {**{k: v for k, v in source.items() if k != 'dicom_files'},
                         'input_path': request['input_path']},
              'masks': masks, 'status': 'empty' if not any(m['voxels'] for m in masks) else 'completed'}
    (job_dir / 'manifest.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('Máscaras conferidas e manifesto gravado.', flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--job-dir', required=True, type=Path)
    parser.add_argument('--models-dir', required=True, type=Path)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding='utf-8'))
    run_job(request, args.job_dir, args.models_dir)


if __name__ == '__main__':
    main()

import configparser
import hashlib
import json
from pathlib import Path

RELEASE = '1.2.0'
BASE_URL = f'https://github.com/raidionics/Raidionics-models/releases/download/{RELEASE}/'
MODEL_LOCK = json.loads((Path(__file__).resolve().parents[1] / 'models.lock.json').read_text(encoding='utf-8'))['models']

MODELS = [
    {'id': 'MRI_GBM', 'label': 'Glioblastoma · pré-operatório', 'sequence': 'T1-CE',
     'asset': 'Raidionics-MRI_GBM-ONNX-v12.zip', 'size': 68791937},
    {'id': 'MRI_LGGlioma', 'label': 'Glioma de baixo grau · pré-operatório', 'sequence': 'FLAIR',
     'asset': 'Raidionics-MRI_LGGlioma-ONNX-v12.zip', 'size': 69041134},
    {'id': 'MRI_Meningioma', 'label': 'Meningioma · pré-operatório', 'sequence': 'T1-CE',
     'asset': 'Raidionics-MRI_Meningioma-ONNX-v12.zip', 'size': 68913186},
    {'id': 'MRI_Metastasis', 'label': 'Metástase · pré-operatório', 'sequence': 'T1-CE',
     'asset': 'Raidionics-MRI_Metastasis-ONNX-v12.zip', 'size': 68802585},
    {'id': 'MRI_GBM_Postop_FV_1p', 'label': 'Glioblastoma · pós-operatório (1 sequência)',
     'sequence': 'T1-CE pós-operatória', 'asset': 'Raidionics-MRI_GBM_Postop_FV_1p-ONNX_v12.zip',
     'size': 69216547},
]

BRAIN = {'id': 'MRI_Brain', 'label': 'Máscara cerebral auxiliar', 'sequence': 'RM',
         'asset': 'Raidionics-MRI_Brain-ONNX-v12.zip', 'size': 69134888,
         'classes': ['Background', 'Brain']}


def get_model(model_id):
    for model in MODELS:
        if model['id'] == model_id:
            return dict(model)
    raise ValueError('Modelo não pertence ao catálogo permitido.')


def validate_model_folder(folder, model):
    folder = Path(folder)
    ini = folder / 'pre_processing.ini'
    weights = folder / 'fold0' / 'model.onnx'
    if not ini.is_file() or not weights.is_file() or not weights.stat().st_size:
        raise ValueError(f"Prepare os pesos locais de {model['id']} antes de executar.")
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(ini, encoding='utf-8-sig')
    if cfg.get('Default', 'imaging_modality', fallback='') != 'MRI':
        raise ValueError('O modelo local não declara modalidade MRI.')
    if cfg.getint('PreProcessing', 'number_inputs', fallback=0) != 1:
        raise ValueError('Esta versão aceita modelos de uma sequência por execução.')
    classes = [x.strip() for x in cfg.get('Training', 'classes', fallback='').split(',')]
    if classes != model.get('classes', ['Background', 'Tumor']) or cfg.getint('Training', 'nb_classes', fallback=0) != 2:
        raise ValueError('Classes do peso local não correspondem ao modelo binário permitido.')
    receipt = folder / 'provenance.json'
    if not receipt.is_file():
        raise ValueError('Modelo sem procedência verificada; execute o preparador oficial.')
    recorded = json.loads(receipt.read_text(encoding='utf-8'))
    if recorded.get('model_id') != model['id'] or recorded.get('release') != RELEASE:
        raise ValueError('Procedência não corresponde ao modelo selecionado.')
    for name in ('pre_processing.ini', 'fold0/model.onnx'):
        digest = hashlib.sha256()
        with (folder / name).open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        expected = MODEL_LOCK[model['id']]['files'][name]
        if digest.hexdigest() != expected or recorded.get('files', {}).get(name) != expected:
            raise ValueError('Peso ou metadado local alterado/corrompido; prepare novamente.')
    return classes[1:]


def requires_brain(folder):
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(Path(folder) / 'pre_processing.ini', encoding='utf-8-sig')
    return cfg.get('PreProcessing', 'background_cropping', fallback='') in ('brain_mask', 'brain_clip')


def model_status(root):
    status = []
    for model in MODELS:
        try:
            validate_model_folder(Path(root) / model['id'], model)
            if requires_brain(Path(root) / model['id']):
                validate_model_folder(Path(root) / BRAIN['id'], BRAIN)
            ready, reason = True, ''
        except (ValueError, OSError, configparser.Error) as exc:
            ready, reason = False, str(exc)
        status.append({**model, 'ready': ready, 'reason': reason,
                       'release': RELEASE, 'license': 'BSD-2-Clause'})
    return status

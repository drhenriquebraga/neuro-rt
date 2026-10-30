"""Filesystem-only Buti capability; never imports a scientific runtime.

The host owns the model location, metadata and downloads. Availability here
means the expected files and runtime layout exist; the worker verifies hashes
and imports the engine before inference.
"""
import hashlib
import json
from pathlib import Path
from types import ModuleType

from .host_imports import host_module_path

IDENT = 'cranio_buti'
TRAINER = 'nnUNetTrainer__nnUNetPlans__3d_fullres'
LABELS = {1: 'Brain', 2: 'Brainstem', 3: 'Cerebellum', 4: 'Chiasm',
          5: 'OpticNerve_L', 6: 'OpticNerve_R', 7: 'Ventricles_connected', 8: 'Midline'}
REQUIRED = ('dataset.json', 'plans.json', 'dataset_fingerprint.json',
            'fold_all/checkpoint_final.pth')


def load_host_module(host_app, name):
    """Execute a trusted host source under a private name without pycache writes."""
    if not host_app or str(host_app).strip() == '?':
        raise ValueError('Pasta do host não configurada.')
    path = host_module_path(host_app, name)
    if path is None:
        raise ValueError('Executor/metadados Buti ausentes no host: ' + name)
    module = ModuleType('_neuro_private_' + name)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


def host_assets(host_app, verify_hashes=False):
    models = load_host_module(host_app, 'radai_models')
    metadata = (models.MODELOS or {}).get(IDENT) or {}
    base = Path(models.pasta_do_modelo(IDENT)).resolve()
    trainer = base / TRAINER
    expected_sizes = dict(metadata.get('arquivos') or [])
    hashes = {}
    for name in REQUIRED:
        rel = TRAINER + '/' + name
        path = trainer / name
        compact = (metadata.get('enxuto') or {}).get(rel)
        sizes = [expected_sizes.get(rel)] + ([compact[0]] if compact else [])
        expected = (metadata.get('sha256') or {}).get(rel)
        if (not path.is_file() or path.stat().st_size <= 0
                or path.stat().st_size not in sizes or not expected):
            raise ValueError('Artefato Buti ausente/corrompido no host: ' + name)
        if verify_hashes:
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            actual = digest.hexdigest()
            if actual not in [expected, *([compact[1]] if compact else [])]:
                raise ValueError('Artefato Buti alterado/corrompido no host: ' + name)
            hashes[rel] = actual
    dataset = json.loads((trainer / 'dataset.json').read_text(encoding='utf-8'))
    table = {int(value): str(name) for name, value in (dataset.get('labels') or {}).items()
             if int(value) > 0}
    if table != LABELS or dataset.get('channel_names') != {'0': 'CT'}:
        raise ValueError('As classes/rótulos ou o canal TC do peso Buti divergem do contrato.')
    return base, trainer, table, metadata, hashes


def capabilities(host_app, host_python):
    info = {'available': False, 'reason': '', 'runtime_id': 'host-nnunet',
            'model_dir': '', 'trainer_dir': ''}
    try:
        if not host_python or str(host_python).strip() == '?' or not Path(host_python).is_file():
            raise ValueError('Python do host não configurado ou ausente.')
        python_dir = Path(host_python).resolve().parent
        sites = [python_dir / 'Lib/site-packages', python_dir.parent / 'Lib/site-packages']
        missing = [name for name in ('torch', 'nnunetv2', 'numpy', 'SimpleITK')
                   if not any((site / name).is_dir() for site in sites)]
        if missing:
            raise ValueError('Runtime do host incompleto: ' + ', '.join(missing))
        if host_module_path(host_app, 'radai_cranio_engine') is None:
            raise ValueError('Executor Buti ausente no host.')
        base, trainer, _, _, _ = host_assets(host_app)
        info.update(available=True, model_dir=str(base), trainer_dir=str(trainer))
    except Exception as exc:
        info['reason'] = str(exc) or type(exc).__name__
    return {IDENT: info}

"""Lightweight, versioned Neuro model specifications and artifact verification."""
import copy
import hashlib
import json
import re
from pathlib import Path, PureWindowsPath
from urllib.parse import urlparse

CATALOG = Path(__file__).resolve().parents[1] / 'catalog' / 'models.json'
LICENSES = frozenset(('MIT', 'BSD-2-Clause', 'BSD-3-Clause', 'Apache-2.0',
                      'CC0-1.0', 'CC-BY-4.0'))
GROUPS = frozenset(('glioma', 'metastasis', 'meningioma', 'anatomia', 'auxiliary'))
ROLES = frozenset(('T1', 'T1c', 'T2', 'FLAIR', 'CT'))


def _identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value)


def _relative_path(root, value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or PureWindowsPath(value).is_absolute() or Path(value).is_absolute()):
        raise ValueError('Caminho de artefato inválido.')
    target = (root / value).resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError('Artefato fora da pasta do modelo.')
    return target


def load_catalog(path=CATALOG):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema') != 'neuro-rt/catalog/1':
        raise ValueError('Schema do catálogo inválido.')
    models = data.get('models')
    if not isinstance(models, list) or not models:
        raise ValueError('Catálogo vazio ou inválido.')
    seen = set()
    for model in models:
        if not isinstance(model, dict) or not _identifier(model.get('id')):
            raise ValueError('ID de modelo inválido.')
        if model['id'] in seen:
            raise ValueError('ID de modelo duplicado.')
        seen.add(model['id'])
        if model.get('catalog_state') not in ('distributed', 'verified', 'candidate'):
            raise ValueError('Estado de catálogo inválido.')
        if (not isinstance(model.get('groups'), list) or not model['groups']
                or not set(model['groups']).issubset(GROUPS)):
            raise ValueError('Grupo de modelo inválido.')
        license_info = model.get('license', {})
        if (not isinstance(license_info, dict) or license_info.get('code') not in LICENSES
                or license_info.get('weights') not in LICENSES):
            raise ValueError('Licença fora do catálogo comercial permitido.')
        sources = license_info.get('sources')
        if not isinstance(sources, list) or not sources or any(
                not isinstance(url, str) or urlparse(url).scheme != 'https'
                or not urlparse(url).netloc for url in sources):
            raise ValueError('Fonte da licença ausente ou inválida.')
        channels = model.get('channels')
        if not isinstance(channels, list) or not channels or any(
                not isinstance(ch, dict) or ch.get('role') not in ROLES for ch in channels):
            raise ValueError('Canais de entrada inválidos.')
        if len({ch['role'] for ch in channels}) != len(channels):
            raise ValueError('Canais de entrada duplicados.')
        classes = model.get('classes')
        if not isinstance(classes, list) or any(
                not isinstance(c, dict) or not _identifier(c.get('class_id')) for c in classes):
            raise ValueError('Classes de saída inválidas.')
        if len({c['class_id'] for c in classes}) != len(classes):
            raise ValueError('Classes de saída duplicadas.')
        if model['catalog_state'] in ('distributed', 'verified') and (
                not model.get('revision') or not classes or not model.get('artifacts')):
            raise ValueError('Modelo anunciado sem revisão, classes ou artefatos fixados.')
    return copy.deepcopy(models)


def get_model_spec(model_id, path=CATALOG):
    for model in load_catalog(path):
        if model['id'] == model_id:
            return model
    raise ValueError('Modelo não pertence ao catálogo Neuro.')


def verify_artifacts(model_spec, paths):
    model_id = model_spec.get('id')
    report = {'model_id': model_id, 'revision': model_spec.get('revision'),
              'status': 'corrupt', 'verified_files': [], 'missing_files': [], 'errors': []}
    try:
        if not _identifier(model_id):
            raise ValueError('ID de modelo inválido.')
        if model_spec.get('catalog_state') == 'candidate':
            report['status'] = 'candidate'
            return report
        if model_spec.get('catalog_state') not in ('distributed', 'verified'):
            raise ValueError('Estado do modelo inválido.')
        base = Path(getattr(paths, 'models_dir', paths)).resolve()
        folder = _relative_path(base, model_spec.get('artifact_subdir', model_id))
        artifacts = model_spec.get('artifacts')
        if not isinstance(artifacts, list) or not artifacts:
            raise ValueError('Modelo sem artefatos fixados.')
        for artifact in artifacts:
            file = _relative_path(folder, artifact.get('path'))
            digest = artifact.get('sha256')
            if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError('Artefato sem SHA-256 fixado.')
            if not file.is_file():
                report['missing_files'].append(artifact['path'])
                continue
            with file.open('rb') as stream:
                head = stream.read(256).lstrip().lower()
                if head.startswith((b'<!doctype html', b'<html')):
                    raise ValueError('Download contém HTML em vez do artefato.')
                stream.seek(0)
                computed = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    computed.update(chunk)
            if computed.hexdigest() != digest or (
                    artifact.get('size') is not None and file.stat().st_size != artifact['size']):
                raise ValueError('Artefato não corresponde à identidade fixada.')
            report['verified_files'].append(artifact['path'])
        report['status'] = 'missing' if report['missing_files'] else 'ready'
    except (ValueError, OSError, TypeError, AttributeError) as exc:
        report['errors'].append(str(exc))
    return report

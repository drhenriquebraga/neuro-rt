"""Private, immutable study revisions and a deliberately small public projection.

Only the service creates manifests and registers job directories. Neither a UI
ticket nor an artifact ID is interpreted as a client filesystem path.
"""
import copy
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import threading
import uuid

from .contracts import _series, validate_identifier, validate_model_result
from .model_registry import load_catalog
from .integrity import sha256_file
from .study_types import (ContractMessage, ContractRecord, EXECUTION_STATUSES,
                          EXPORT_STATUSES, ExportReceipt, StudyManifest)

ACTIVE = frozenset(('queued', 'preparing', 'running', 'restoring', 'exporting', 'visualizing'))
MEDIA = {'.nii.gz': 'application/gzip', '.nii': 'application/octet-stream',
         '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
         '.stl': 'model/stl', '.glb': 'model/gltf-binary', '.json': 'application/json',
         '.dcm': 'application/dicom', '.svg': 'image/svg+xml', '.js': 'text/javascript'}
LOGICAL_NAME = re.compile(r'(?:view\.json|renderer\.js|(?:axial|coronal|sagittal)_'
                          r'[0-9]{3,5}\.svg|roi_[0-9]{3,5}\.stl)')


def _id(value):
    return validate_identifier(value)


def atomic_json(path, data):
    """Replace one JSON file after writing and flushing it on the same volume."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8', newline='\n') as handle:
            json.dump(data, handle, ensure_ascii=False, allow_nan=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_manifest(manifest, catalog=None):
    """Validate private v2 records without importing image/runtime libraries."""
    data = manifest.to_dict() if isinstance(manifest, StudyManifest) else copy.deepcopy(manifest)
    if not isinstance(data, dict) or data.get('schema') != 'neuro-rt/result/2':
        raise ValueError('Manifesto de estudo v2 obrigatório.')
    json.dumps(data, allow_nan=False)
    allowed = set(StudyManifest.__dataclass_fields__)
    if set(data) - allowed:
        raise ValueError('Campo fora do contrato de resultado.')
    for name in ('study_id', 'request_id', 'plugin_version'):
        _id(data.get(name))
    if type(data.get('revision')) is not int or data['revision'] < 1:
        raise ValueError('Revisão inválida.')
    if data.get('approval_status', 'UNAPPROVED') != 'UNAPPROVED':
        raise ValueError('A sugestão deve permanecer UNAPPROVED.')
    reference = data.get('reference')
    if not isinstance(reference, dict):
        raise ValueError('Descritor de referência obrigatório.')
    ticket = _id(reference.get('ticket'))
    descriptor = _series(ticket, {ticket: reference})
    requested = data.get('requested_model_ids')
    if (not isinstance(requested, list) or not requested or
            len(set(requested)) != len(requested)):
        raise ValueError('Lista de modelos inválida.')
    catalog = catalog if catalog is not None else {m['id']: m for m in load_catalog()}
    for model_id in requested:
        _id(model_id)
        if model_id not in catalog:
            raise ValueError('Modelo fora do catálogo permitido.')
    if not isinstance(data.get('results'), list):
        raise ValueError('Lista de resultados obrigatória.')
    results, seen = [], set()
    for result in data['results']:
        mid = result.get('model_id') if isinstance(result, dict) else None
        if mid not in requested or mid in seen:
            raise ValueError('Modelo não solicitado ou duplicado no resultado.')
        seen.add(mid)
        results.append(validate_model_result(result, catalog[mid]))
    if data.get('status') not in EXECUTION_STATUSES:
        raise ValueError('Estado do estudo inválido.')
    if data['status'] in ('completed', 'empty') and (
            seen != set(requested) or any(r.status not in ('completed', 'empty') for r in results)
            or data['status'] == 'empty' and any(r.masks for r in results)):
        raise ValueError('Conclusão completa exige resultado de todos os modelos solicitados.')
    if data.get('export_status', 'pending') not in EXPORT_STATUSES:
        raise ValueError('Estado de exportação inválido.')
    if (data.get('device_preference') not in ('auto', 'cpu', 'cuda') or
            data.get('effective_device') not in ('cpu', 'cuda') or
            data['device_preference'] in ('cpu', 'cuda') and
            data['device_preference'] != data['effective_device']):
        raise ValueError('Dispositivo efetivo incompatível com a preferência.')
    receipt = data.get('export_receipt')
    if receipt is not None:
        if (not isinstance(receipt, dict) or set(receipt) != set(ExportReceipt.__dataclass_fields__)
                or not all(isinstance(receipt.get(k), str) for k in
                           ('published_file', 'sop_instance_uid', 'reference'))
                or receipt['reference'] != ticket or type(receipt.get('revision')) is not int
                or receipt['revision'] < 1):
            raise ValueError('Recibo de exportação inválido.')
        for key in ('delivered_rois', 'omitted_rois'):
            if not isinstance(receipt.get(key), list) or any(
                    not isinstance(v, str) for v in receipt[key]):
                raise ValueError('Identidades de ROI inválidas no recibo.')
        receipt = ExportReceipt(**receipt)
    if data.get('export_status') == 'completed' and (
            receipt is None or not receipt.published_file or not receipt.sop_instance_uid
            or receipt.omitted_rois):
        raise ValueError('Exportação completa exige recibo publicado sem omissões.')
    artifacts = data.get('artifacts', [])
    if not isinstance(artifacts, list) or any(not isinstance(a, dict) for a in artifacts):
        raise ValueError('Lista de artefatos inválida.')
    for artifact in artifacts:
        if (set(artifact) - {'artifact_id', 'path', 'kind', 'media_type', 'sha256', 'logical_name'} or
                artifact.get('kind') not in ('mask', 'view', 'slice', 'mesh', 'rtstruct') or
                not isinstance(artifact.get('path'), str)):
            raise ValueError('Registro de artefato fora da lista permitida.')
        if 'artifact_id' in artifact and not re.fullmatch(r'a[0-9a-f]{32}',
                                                        str(artifact['artifact_id'])):
            raise ValueError('Identificador de artefato deve ser opaco.')
        if 'media_type' in artifact and artifact['media_type'] not in MEDIA.values():
            raise ValueError('Tipo de mídia não autorizado.')
        if 'logical_name' in artifact and (not isinstance(artifact['logical_name'], str)
                or not LOGICAL_NAME.fullmatch(artifact['logical_name'])
                or _suffix(Path(artifact['logical_name'])) != _suffix(Path(artifact['path']))):
            raise ValueError('Nome lógico de visualização fora da lista permitida.')
    return StudyManifest(data['request_id'], data['study_id'], data['plugin_version'],
                         data['revision'], descriptor, requested, results, data['status'],
                         data['device_preference'], data['effective_device'],
                         data.get('export_status', 'pending'), receipt, artifacts)


@dataclass(frozen=True)
class StudyView(ContractRecord):
    study_id: str
    request_id: str
    revision: int
    reference_ticket: str
    status: str
    export_status: str
    requested_model_ids: list
    models: list
    artifacts: list
    approval_status: str = 'UNAPPROVED'


@dataclass(frozen=True)
class AuthorizedArtifact:
    artifact_id: str
    path: Path
    media_type: str
    kind: str
    revision: int


def public_view(manifest, catalog=None):
    """Project a previously validated server record; never copy free-form metadata."""
    manifest = validate_manifest(manifest, catalog)
    artifacts = [{'artifact_id': a['artifact_id'], 'kind': a['kind'],
                  'media_type': a['media_type'],
                  **({'logical_name': a['logical_name']} if 'logical_name' in a else {})}
                 for a in manifest.artifacts
                 if all(k in a for k in ('artifact_id', 'kind', 'media_type'))]
    models = [{'model_id': r.model_id, 'status': r.status,
               'classes': [m.class_id for m in r.masks],
               'warning_count': len(r.warnings), 'error_count': len(r.errors)}
              for r in manifest.results]
    return StudyView(manifest.study_id, manifest.request_id, manifest.revision,
                     manifest.reference.ticket, manifest.status, manifest.export_status,
                     list(manifest.requested_model_ids), models, artifacts)


def _suffix(path):
    return '.nii.gz' if path.name.lower().endswith('.nii.gz') else path.suffix.lower()


class ResultStore:
    def __init__(self, data_dir, *, catalog=None):
        self.data_dir = Path(data_dir).resolve()
        self.root = self.data_dir / 'studies'
        self.root.mkdir(parents=True, exist_ok=True)
        self.catalog = catalog if catalog is not None else {m['id']: m for m in load_catalog()}
        self._jobs = {}
        self._lock = threading.RLock()
        self._recover()

    def register_job(self, study_id, job_dir):
        """Service-only binding; jobs must stay under this store's private jobs root."""
        _id(study_id)
        target = Path(job_dir).resolve()
        if not target.is_relative_to((self.data_dir / 'jobs').resolve()):
            raise ValueError('Pasta privada do estudo fora do diretório de jobs.')
        self._jobs[study_id] = target

    def _study(self, study_id):
        path = (self.root / _id(study_id)).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError('Estudo fora do acervo privado.')
        return path

    def _read(self, path):
        manifest = validate_manifest(json.loads(path.read_text(encoding='utf-8')), self.catalog)
        if manifest.study_id != path.parents[2].name or manifest.revision != int(path.parent.name):
            raise ValueError('Identidade da revisão inconsistente.')
        for result in manifest.results:
            for mask in result.masks:
                self._artifact_source(mask.path, manifest.study_id, 'mask')
        for artifact in manifest.artifacts:
            self._artifact_source(artifact['path'], manifest.study_id, artifact['kind'])
        return manifest

    def _valid_revisions(self, study_id):
        base = self._study(study_id) / 'revisions'
        found = []
        if base.is_dir():
            for revision in base.iterdir():
                if revision.is_dir() and re.fullmatch(r'[1-9][0-9]*', revision.name):
                    try:
                        if not revision.resolve().is_relative_to(base.resolve()):
                            continue
                        found.append((int(revision.name), self._read(revision / 'manifest.json')))
                    except (OSError, ValueError, TypeError, KeyError):
                        continue
        return sorted(found, key=lambda item: item[0])

    def load_manifest(self, study_id, revision=None):
        _id(study_id)
        if revision is not None and (type(revision) is not int or revision < 1):
            raise ValueError('Revisão inválida.')
        revisions = self._valid_revisions(study_id)
        if revision is not None:
            revisions = [r for r in revisions if r[0] == revision]
        if not revisions:
            raise FileNotFoundError('Resultado autorizado não encontrado.')
        return revisions[-1][1]

    def _artifact_source(self, path, study_id, kind=None):
        if not isinstance(path, str) or not path or '\\' in path and not Path(path).is_absolute():
            raise ValueError('Caminho privado de artefato inválido.')
        job = self._jobs.get(study_id, (self.data_dir / 'jobs' / study_id).resolve())
        raw = Path(path)
        if not raw.is_absolute() and (':' in path or PureWindowsPath(path).is_absolute()
                                      or '..' in raw.parts):
            raise ValueError('Caminho privado de artefato inválido.')
        target = raw.resolve() if raw.is_absolute() else (job / raw).resolve()
        revision_root = (self._study(study_id) / 'revisions').resolve()
        if target.is_relative_to(job):
            relative = target.relative_to(job)
            allowed = (len(relative.parts) >= 2 and relative.parts[0] in
                       ('masks', 'models', 'views', 'exports', 'export'))
            allowed = allowed or relative.as_posix() == 'RS_NeuroRT.dcm'
        elif target.is_relative_to(revision_root):
            relative = target.relative_to(revision_root)
            allowed = (len(relative.parts) == 3 and relative.parts[0].isdigit()
                       and relative.parts[1] == 'artifacts')
        else:
            allowed = False
        if not allowed or _suffix(target) not in MEDIA:
            raise ValueError('Artefato fora da lista permitida.')
        extensions = {'mask': ('.nii', '.nii.gz'), 'view': ('.png', '.jpg', '.jpeg', '.json', '.js'),
                      'slice': ('.svg',),
                      'mesh': ('.stl', '.glb'), 'rtstruct': ('.dcm',)}
        if kind is not None:
            if kind not in extensions or _suffix(target) not in extensions[kind]:
                raise ValueError('Conteúdo incompatível com o tipo de artefato.')
            if target.is_relative_to(job):
                top = target.relative_to(job).parts[0]
                if kind in ('view', 'slice', 'mesh') and top != 'views':
                    raise ValueError('Visualização fora da pasta de artefatos públicos.')
                if kind == 'rtstruct' and top not in ('export', 'exports', 'RS_NeuroRT.dcm'):
                    raise ValueError('RTSTRUCT fora da pasta de exportação.')
        return target

    def save_manifest(self, manifest):
        manifest = validate_manifest(manifest, self.catalog)
        with self._lock:
            base = self._study(manifest.study_id) / 'revisions'
            base.mkdir(parents=True, exist_ok=True)
            # Reserve monotonically even when a previous revision was damaged.
            numbers = [int(p.name) for p in base.iterdir() if p.name.isdigit()]
            revision = max(numbers, default=0) + 1
            destination = base / str(revision)
            pending = base / ('.pending-' + uuid.uuid4().hex)
            (pending / 'artifacts').mkdir(parents=True)
            data, artifacts, by_source = manifest.to_dict(), [], {}

            def stage(source_path, kind, logical_name=None):
                source = self._artifact_source(source_path, manifest.study_id, kind)
                if source in by_source:
                    return by_source[source]
                if not source.is_file():
                    raise FileNotFoundError('Artefato privado ausente.')
                artifact_id = 'a' + uuid.uuid4().hex
                filename = artifact_id + _suffix(source)
                staged = pending / 'artifacts' / filename
                shutil.copyfile(source, staged)
                digest = sha256_file(staged)
                record = {'artifact_id': artifact_id, 'kind': kind,
                          'media_type': MEDIA[_suffix(source)],
                          'path': str(destination / 'artifacts' / filename), 'sha256': digest}
                if logical_name is not None:
                    record['logical_name'] = logical_name
                artifacts.append(record)
                by_source[source] = record
                return record

            try:
                for result in data['results']:
                    for mask in result['masks']:
                        record = stage(mask['path'], 'mask')
                        if _suffix(Path(mask['path'])) not in ('.nii', '.nii.gz'):
                            raise ValueError('Artefato de máscara precisa ser NIfTI.')
                        mask['path'] = record['path']
                for artifact in data['artifacts']:
                    if artifact.get('kind') not in ('mask', 'view', 'slice', 'mesh', 'rtstruct'):
                        raise ValueError('Tipo de artefato não autorizado.')
                    stage(artifact.get('path'), artifact['kind'], artifact.get('logical_name'))
                data.update(revision=revision, artifacts=artifacts)
                if data.get('export_receipt') is not None:
                    data['export_receipt']['revision'] = revision
                atomic_json(pending / 'manifest.json', data)
                os.rename(pending, destination)
                # Optional cache only: recovery always scans valid manifests.
                atomic_json(self._study(manifest.study_id) / 'latest.json', {'revision': revision})
            except Exception:
                # Uncommitted preparation is harmless and ignored after restart.
                raise
            return revision

    def public_view(self, manifest):
        return public_view(manifest, self.catalog)

    def list_results(self, reference_ticket=None, *, all_revisions=False):
        if reference_ticket is not None:
            _id(reference_ticket)
        results = []
        for directory in sorted(self.root.iterdir()):
            if not directory.is_dir():
                continue
            try:
                manifests = ([m for _, m in self._valid_revisions(directory.name)] if all_revisions
                             else [self.load_manifest(directory.name)])
            except (ValueError, FileNotFoundError):
                continue
            for manifest in manifests:
                if reference_ticket is None or manifest.reference.ticket == reference_ticket:
                    results.append(self.public_view(manifest).to_dict())
        return results

    def resolve_artifact(self, study_id, artifact_id):
        _id(study_id)
        if not isinstance(artifact_id, str) or not re.fullmatch(r'a[0-9a-f]{32}', artifact_id):
            raise ValueError('ID de artefato inválido.')
        for revision, manifest in reversed(self._valid_revisions(study_id)):
            for artifact in manifest.artifacts:
                if artifact.get('artifact_id') != artifact_id:
                    continue
                target = self._artifact_source(artifact['path'], study_id, artifact['kind'])
                expected = (self._study(study_id) / 'revisions' / str(revision) /
                            'artifacts' / (artifact_id + _suffix(target))).resolve()
                if target != expected or not target.is_file():
                    raise FileNotFoundError('Artefato autorizado indisponível.')
                if sha256_file(target) != artifact.get('sha256'):
                    raise ValueError('Artefato autorizado alterado.')
                return AuthorizedArtifact(artifact_id, target, artifact['media_type'],
                                          artifact['kind'], revision)
        raise FileNotFoundError('Artefato autorizado não encontrado.')

    def _recover(self):
        for directory in list(self.root.iterdir()):
            if not directory.is_dir():
                continue
            try:
                manifest = self.load_manifest(directory.name)
                if manifest.status not in ACTIVE:
                    continue
                results = []
                for result in manifest.results:
                    retained = [mask for mask in result.masks if
                        self._artifact_source(mask.path, manifest.study_id, 'mask').is_file()]
                    if len(retained) != len(result.masks):
                        result = replace(result, masks=retained,
                            status='partial' if retained else 'failed',
                            errors=result.errors + [ContractMessage(
                                'artifact_unavailable', 'Artefato privado indisponível após reinício.')])
                    if result.status in ACTIVE:
                        result = replace(result, status='partial' if result.masks else 'interrupted',
                            errors=result.errors + [ContractMessage(
                                'execution_interrupted', 'Execução interrompida; retentativa exige solicitação.')])
                    results.append(result)
                artifacts = [artifact for artifact in manifest.artifacts if
                    self._artifact_source(artifact['path'], manifest.study_id,
                                          artifact['kind']).is_file()]
                self.save_manifest(replace(manifest, status='interrupted', results=results,
                    artifacts=artifacts,
                    export_status='failed' if manifest.export_status == 'pending' else manifest.export_status))
            except (ValueError, OSError, TypeError, KeyError):
                continue

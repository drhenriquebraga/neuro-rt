"""Versioned request/result metadata contracts, independent of image runtimes."""
from collections.abc import Mapping
from dataclasses import replace
import json
import math
from pathlib import Path

from .catalog import get_model
from .study_types import (ContractMessage, EXECUTION_STATUSES, InputBinding,
                          MaskArtifact, ModelResult, SeriesDescriptor, StudyItem,
                          StudyRequest)


def validate_request(request):
    if not isinstance(request, dict) or request.get('explicit_request') is not True:
        raise ValueError('A segmentação de achado exige solicitação explícita.')
    get_model(request.get('model', ''))
    if not isinstance(request.get('input_path'), str) or not request['input_path'].strip():
        raise ValueError('Informe o caminho da RM NIfTI ou da pasta DICOM.')
    if request.get('device', 'auto') not in ('auto', 'cpu', 'cuda'):
        raise ValueError('Preferência de processamento inválida.')
    if not isinstance(request.get('export_rtstruct', False), bool):
        raise ValueError('Opção de RTSTRUCT inválida.')
    if not isinstance(request.get('series_uid', ''), str):
        raise ValueError('SeriesInstanceUID inválido.')
    return {**request, 'input_path': str(Path(request['input_path'].strip()).resolve()),
            'series_uid': request.get('series_uid', '').strip(),
            'device': request.get('device', 'auto'),
            'export_rtstruct': request.get('export_rtstruct', False)}


class ContractError(ValueError):
    """Stable machine-readable failure, with a non-identifying field path."""
    def __init__(self, code, field, message):
        self.code = code
        self.field = field
        super().__init__(message)


def _fail(code, field, message):
    raise ContractError(code, field, message)


def _json_value(value, field):
    """Reject silent JSON coercion (tuple, nonstring key, NaN, custom object)."""
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if isinstance(value, list):
        for entry in value:
            _json_value(entry, field)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for entry in value.values():
            _json_value(entry, field)
        return
    _fail('invalid_json', field, 'O contrato exige valores JSON finitos e chaves de texto.')


def _object(value, field):
    if not isinstance(value, dict):
        _fail('invalid_type', field, 'Informe um objeto no campo indicado.')
    return value


def _array(value, field):
    if not isinstance(value, list):
        _fail('invalid_type', field, 'Informe uma lista no campo indicado.')
    return value


def _text(value, field, allow_empty=False):
    if not isinstance(value, str):
        _fail('invalid_type', field, 'Informe texto no campo indicado.')
    if not allow_empty and (not value.strip() or value != value.strip()):
        _fail('invalid_identifier', field, 'Identificador ausente ou com espaços nas extremidades.')
    return value


def _fields(value, allowed, field):
    if set(value) - set(allowed):
        _fail('unexpected_field', field, 'O objeto contém campos fora deste contrato.')


def _metadata(value, field):
    _object(value, field)
    _json_value(value, field)
    return json.loads(json.dumps(value, allow_nan=False))


def _messages(value, field):
    records = []
    for entry in _array(value, field):
        _object(entry, field)
        _fields(entry, ('code', 'message', 'details'), field)
        records.append(ContractMessage(_text(entry.get('code'), field),
                                       _text(entry.get('message'), field),
                                       _metadata(entry.get('details', {}), field)))
    return records


def _series(ticket, series_index):
    _text(ticket, 'series_ticket')
    if ticket not in series_index:
        _fail('unknown_series', 'series_ticket', 'Série/ticket não pertence ao inventário autorizado.')
    source = series_index[ticket]
    data = source.to_dict() if isinstance(source, SeriesDescriptor) else source
    _object(data, 'series_index')
    _json_value(data, 'series_index')
    for key in ('ticket', 'series_uid', 'subject_key', 'study_key', 'modality'):
        _text(data.get(key), 'series_index.' + key, allow_empty=key == 'series_uid')
    if data['ticket'] != ticket or data.get('source_format', 'dicom') not in ('dicom', 'nifti'):
        _fail('invalid_series', 'series_index', 'Descritor não corresponde ao ticket/formato.')
    source_format = data.get('source_format', 'dicom')
    if source_format == 'dicom' and not data['series_uid']:
        _fail('invalid_series', 'series_index.series_uid', 'Série DICOM exige UID declarado.')
    if source_format == 'nifti' and (data['series_uid'] or data.get('frame_of_reference_uid')
                                    or data.get('sop_instance_uids')):
        _fail('invalid_series', 'series_index', 'NIfTI sem DICOM não pode declarar referências DICOM.')
    uids = _array(data.get('sop_instance_uids', []), 'series_index.sop_instance_uids')
    for uid in uids:
        _text(uid, 'series_index.sop_instance_uids')
    candidates = _array(data.get('sequence_candidates', []), 'series_index.sequence_candidates')
    for candidate in candidates:
        _object(candidate, 'series_index.sequence_candidates')
    return SeriesDescriptor(ticket=ticket, series_uid=data['series_uid'],
                            subject_key=data['subject_key'], study_key=data['study_key'],
                            modality=data['modality'], source_format=source_format,
                            geometry=_metadata(data.get('geometry', {}), 'series_index.geometry'),
                            sequence_candidates=json.loads(json.dumps(candidates)),
                            frame_of_reference_uid=_text(data.get('frame_of_reference_uid', ''),
                                                         'series_index.frame_of_reference_uid', True),
                            sop_instance_uids=list(uids))


def _model(model_id, catalog):
    if model_id not in catalog:
        _fail('unknown_model', 'model_ids', 'Modelo não pertence ao catálogo permitido.')
    spec = _object(catalog[model_id], 'catalog')
    if spec.get('id') != model_id:
        _fail('invalid_catalog', 'catalog.id', 'Identidade do modelo inconsistente no catálogo.')
    return spec


def _roles(spec):
    channels = _array(spec.get('channels'), 'catalog.channels')
    roles = [_text(_object(c, 'catalog.channels').get('role'), 'catalog.channels.role')
             for c in channels]
    if not roles or len(set(roles)) != len(roles):
        _fail('invalid_catalog', 'catalog.channels', 'O modelo exige canais distintos e ordenados.')
    return roles


def _series_identity(descriptor):
    # Resolve aliases by declared DICOM identity, never by ticket spelling/path.
    return ((descriptor.source_format, descriptor.series_uid)
            if descriptor.source_format == 'dicom' else ('nifti', descriptor.ticket))


def validate_study_request(payload, catalog, series_index) -> StudyRequest:
    """Validate a v2 intent against a trusted model catalog and ticket inventory.

    This validates structural eligibility only. D02 owns sequence suggestions and
    capabilities; D04 owns idempotency storage (request_id is never generated here).
    Binding uncertainty is preserved and never treated as an absent input.
    """
    _object(payload, 'request')
    if payload.get('explicit_request') is not True:
        _fail('explicit_request_required', 'explicit_request',
              'A segmentação exige solicitação explícita.')
    _json_value(payload, 'request')
    _fields(payload, ('schema', 'request_id', 'explicit_request', 'studies', 'device',
                      'export_rtstruct'), 'request')
    if payload.get('schema') != 'neuro-rt/request/2':
        _fail('unsupported_schema', 'schema', 'Versão do contrato de pedido não suportada.')
    request_id = _text(payload.get('request_id'), 'request_id')
    if not isinstance(catalog, Mapping) or not isinstance(series_index, Mapping):
        _fail('invalid_type', 'catalog/series_index', 'Catálogo e inventário devem ser mapeamentos.')
    device = payload.get('device', 'auto')
    if device not in ('auto', 'cpu', 'cuda'):
        _fail('invalid_device', 'device', 'Preferência de processamento inválida.')
    export = payload.get('export_rtstruct', False)
    if type(export) is not bool:
        _fail('invalid_type', 'export_rtstruct', 'Opção de RTSTRUCT deve ser booleana.')
    studies = _array(payload.get('studies'), 'studies')
    if not studies:
        _fail('empty_studies', 'studies', 'O pedido exige pelo menos um estudo.')
    items, references, study_ids = [], set(), set()
    for item in studies:
        _object(item, 'studies')
        _fields(item, ('study_id', 'reference', 'model_ids', 'bindings_by_model',
                       'legacy_input_path'), 'studies')
        if item.get('legacy_input_path') is not None:
            _fail('legacy_only', 'legacy_input_path', 'Caminhos são restritos ao adaptador v1.')
        study_id = _text(item.get('study_id'), 'study_id')
        if study_id in study_ids:
            _fail('duplicate_study', 'study_id', 'O pedido repete um identificador de estudo.')
        study_ids.add(study_id)
        reference = _series(item.get('reference'), series_index)
        identity = _series_identity(reference)
        if identity in references:
            _fail('duplicate_reference', 'reference', 'A referência aparece em mais de um item.')
        references.add(identity)
        if export and reference.source_format != 'dicom':
            _fail('dicom_reference_required', 'export_rtstruct',
                  'RTSTRUCT exige a série DICOM original de referência.')
        model_ids = [_text(mid, 'model_ids') for mid in _array(item.get('model_ids'), 'model_ids')]
        if not model_ids:
            _fail('empty_models', 'model_ids', 'Escolha pelo menos um modelo explicitamente.')
        if len(set(model_ids)) != len(model_ids):
            _fail('duplicate_model', 'model_ids', 'O item repete um modelo.')
        specs = {mid: _model(mid, catalog) for mid in model_ids}
        supplied = _object(item.get('bindings_by_model'), 'bindings_by_model')
        if set(supplied) - set(model_ids):
            _fail('unexpected_bindings', 'bindings_by_model', 'Bindings para modelo não solicitado.')
        if set(model_ids) - set(supplied):
            _fail('missing_bindings', 'bindings_by_model', 'Faltam bindings de um modelo solicitado.')
        bindings = {}
        for model_id in model_ids:
            roles, by_role, input_ids = _roles(specs[model_id]), {}, set()
            for raw in _array(supplied[model_id], 'bindings_by_model'):
                _object(raw, 'binding')
                _fields(raw, ('role', 'series_ticket', 'certainty', 'association_source', 'warnings'),
                        'binding')
                role = _text(raw.get('role'), 'binding.role')
                if role in by_role:
                    _fail('duplicate_role', 'binding.role', 'O modelo repete um papel de entrada.')
                if role not in roles:
                    _fail('unexpected_role', 'binding.role', 'Papel não faz parte dos canais do modelo.')
                descriptor = _series(raw.get('series_ticket'), series_index)
                if descriptor.subject_key != reference.subject_key:
                    _fail('inconsistent_subject', 'binding.series_ticket', 'Entradas pertencem a sujeitos diferentes.')
                if descriptor.study_key != reference.study_key:
                    _fail('inconsistent_study', 'binding.series_ticket', 'Entradas pertencem a estudos diferentes.')
                if descriptor.modality != reference.modality:
                    _fail('inconsistent_modality', 'binding.series_ticket',
                          'Entradas e referência não podem transferir RM–TC implicitamente.')
                source_id = _series_identity(descriptor)
                if source_id in input_ids:
                    _fail('duplicate_input', 'binding.series_ticket', 'Uma série não pode substituir dois canais.')
                input_ids.add(source_id)
                certainty = raw.get('certainty', 'unknown')
                association_source = raw.get('association_source', 'manual')
                if certainty not in ('certain', 'uncertain', 'unknown'):
                    _fail('invalid_certainty', 'binding.certainty', 'Certeza da classificação inválida.')
                if association_source not in ('manual', 'suggested', 'legacy'):
                    _fail('invalid_association_source', 'binding.association_source', 'Origem da associação inválida.')
                by_role[role] = InputBinding(role, descriptor.ticket, certainty, association_source,
                                             _messages(raw.get('warnings', []), 'binding.warnings'))
            if set(roles) - set(by_role):
                _fail('missing_roles', 'bindings_by_model', 'Falta uma entrada obrigatória do modelo.')
            bindings[model_id] = [by_role[role] for role in roles]
        items.append(StudyItem(study_id, reference.ticket, list(model_ids), bindings))
    return StudyRequest(request_id, True, items, device, export)


def _class_key(class_id):
    # bool is an int subclass; do not allow True to silently become class 1.
    if type(class_id) is int and class_id >= 0:
        return (int, class_id)
    if type(class_id) is str and class_id.strip() and class_id == class_id.strip():
        return (str, class_id)
    _fail('unknown_class', 'class_id', 'Identificador de classe inválido.')


def _classes(spec):
    classes = {}
    for entry in _array(spec.get('classes'), 'catalog.classes'):
        _object(entry, 'catalog.classes')
        key = _class_key(entry.get('class_id'))
        if key in classes:
            _fail('invalid_catalog', 'catalog.classes', 'O catálogo repete uma classe.')
        classes[key] = entry
    if not classes:
        _fail('invalid_catalog', 'catalog.classes', 'O artefato não declara classes de saída.')
    return classes


def _string_map(value, field):
    data = _metadata(value, field)
    for key, entry in data.items():
        _text(key, field)
        _text(entry, field)
    return data


def validate_model_result(result, model_spec) -> ModelResult:
    """Validate adapter metadata and stable model/class identity, without image I/O.

    D03 still has to check actual geometry/label voxels and transform application.
    Multiple masks for the same class are not allowed: preserve all its foci in
    one artifact instead of silently selecting a component.
    """
    if isinstance(result, ModelResult):
        result = result.to_dict()
    _object(result, 'result')
    _json_value(result, 'result')
    _fields(result, ('model_id', 'status', 'masks', 'geometry', 'transformations', 'versions',
                     'hashes', 'warnings', 'errors'), 'result')
    _object(model_spec, 'model_spec')
    model_id = _text(result.get('model_id'), 'result.model_id')
    if model_id != model_spec.get('id'):
        _fail('model_mismatch', 'result.model_id', 'O resultado não pertence ao modelo esperado.')
    allowed = _classes(model_spec)
    status = result.get('status')
    if not isinstance(status, str) or status not in EXECUTION_STATUSES:
        _fail('invalid_status', 'result.status', 'Estado de execução não reconhecido.')
    masks, seen = [], set()
    for raw in _array(result.get('masks', []), 'result.masks'):
        _object(raw, 'mask')
        _fields(raw, ('model_id', 'class_id', 'path', 'geometry', 'space', 'provenance'), 'mask')
        if raw.get('model_id') != model_id:
            _fail('model_mismatch', 'mask.model_id', 'A máscara não pertence ao modelo esperado.')
        key = _class_key(raw.get('class_id'))
        if key not in allowed:
            _fail('unknown_class', 'mask.class_id', 'Classe não corresponde ao manifesto do artefato.')
        if key in seen:
            _fail('duplicate_class', 'mask.class_id', 'O resultado repete uma classe de saída.')
        seen.add(key)
        masks.append(MaskArtifact(model_id, raw['class_id'], _text(raw.get('path'), 'mask.path'),
                                  _metadata(raw.get('geometry', {}), 'mask.geometry'),
                                  _text(raw.get('space', 'reference'), 'mask.space'),
                                  _metadata(raw.get('provenance', {}), 'mask.provenance')))
    transformations = [_metadata(t, 'result.transformations') for t in
                       _array(result.get('transformations', []), 'result.transformations')]
    errors = _messages(result.get('errors', []), 'result.errors')
    if ((status == 'completed' and (not masks or errors)) or
            (status == 'empty' and (masks or errors)) or
            (status in ('failed', 'interrupted') and (masks or not errors)) or
            (status == 'partial' and (not masks or not errors))):
        _fail('inconsistent_result', 'result.status', 'Estado incompatível com máscaras/erros declarados.')
    return ModelResult(model_id, status, masks,
                       _metadata(result.get('geometry', {}), 'result.geometry'),
                       transformations, _string_map(result.get('versions', {}), 'result.versions'),
                       _string_map(result.get('hashes', {}), 'result.hashes'),
                       _messages(result.get('warnings', []), 'result.warnings'), errors)


def adapt_request_v1(payload, catalog, series_index, *, request_id, study_id,
                     series_ticket) -> StudyRequest:
    """Explicit bridge for the existing single-volume API, not a v2 path bypass.

    The existing importer supplies a trusted descriptor/ticket, including a local
    NIfTI descriptor if no DICOM exists. No UID or multichannel input is inferred.
    Existing v1 consumers can continue calling validate_request unchanged.
    """
    legacy = validate_request(payload)
    spec = _model(legacy['model'], catalog)
    roles = _roles(spec)
    if len(roles) != 1:
        _fail('legacy_multichannel', 'model', 'A API v1 não declara canais multissequência.')
    reference = _series(series_ticket, series_index)
    if legacy['series_uid'] and legacy['series_uid'] != reference.series_uid:
        _fail('reference_mismatch', 'series_uid', 'UID legado não corresponde à referência autorizada.')
    export = legacy['export_rtstruct'] and reference.source_format == 'dicom'
    study = {'study_id': study_id, 'reference': series_ticket,
             'model_ids': [legacy['model']], 'bindings_by_model': {legacy['model']: [
                 {'role': roles[0], 'series_ticket': series_ticket, 'certainty': 'unknown',
                  'association_source': 'legacy', 'warnings': []}]}}
    validated = validate_study_request({'schema': 'neuro-rt/request/2',
                                       'request_id': request_id, 'explicit_request': True,
                                       'studies': [study], 'device': legacy['device'],
                                       'export_rtstruct': export}, catalog, series_index)
    return replace(validated, studies=[replace(validated.studies[0],
                                               legacy_input_path=legacy['input_path'])])


def read_result_v1(result, model_spec) -> ModelResult:
    """Adapt an already-read v1 manifest; never infer IDs or UIDs from filenames.

    Output is a model result, not an invented study/export receipt. Original
    source/RTSTRUCT metadata remains with the caller's v1 manifest until D07.
    """
    _object(result, 'result')
    _json_value(result, 'result')
    if result.get('schema') != 'neuro-rt/result/1':
        _fail('unsupported_schema', 'schema', 'O adaptador exige resultado v1 explícito.')
    model_id = _text(result.get('model_id'), 'result.model_id')
    _object(model_spec, 'model_spec')
    if model_id != model_spec.get('id'):
        _fail('model_mismatch', 'result.model_id', 'O manifesto v1 não pertence ao modelo esperado.')
    declared = _classes(model_spec)
    masks, seen, all_empty = [], set(), True
    for mask in _array(result.get('masks'), 'result.masks'):
        _object(mask, 'result.masks')
        label = _text(mask.get('label'), 'result.masks.label')
        matches = [entry for entry in declared.values() if entry.get('label') == label]
        if len(matches) != 1:
            _fail('unknown_class', 'result.masks.label', 'Classe v1 ausente/ambígua no manifesto do modelo.')
        class_id = matches[0]['class_id']
        key = _class_key(class_id)
        if key in seen:
            _fail('duplicate_class', 'result.masks.label', 'O resultado v1 repete uma classe.')
        seen.add(key)
        path = _text(mask.get('path'), 'result.masks.path')
        voxels = mask.get('voxels')
        if type(voxels) is not int or voxels < 0:
            _fail('invalid_type', 'result.masks.voxels', 'Contagem de voxels v1 inválida.')
        if voxels == 0:
            continue
        all_empty = False
        masks.append({'model_id': model_id, 'class_id': class_id, 'path': path,
                      'geometry': result.get('geometry', {}), 'space': 'reference',
                      'provenance': {'legacy_schema': 'neuro-rt/result/1', 'label': label}})
    status = result.get('status')
    if status == 'empty' and not all_empty:
        _fail('inconsistent_result', 'result.status', 'Resultado v1 vazio declara voxels não vazios.')
    versions = {key: result[name] for key, name in
                (('plugin', 'module_version'), ('model', 'model_release'),
                 ('engine', 'backend_version')) if name in result}
    return validate_model_result({'model_id': model_id, 'status': status, 'masks': masks,
                                  'geometry': result.get('geometry', {}), 'transformations': [],
                                  'versions': versions,
                                  'hashes': {'weights': result['model_sha256']}
                                  if 'model_sha256' in result else {},
                                  'warnings': [{'code': 'LEGACY_V1',
                                                'message': 'Resultado legado; transformações não declaradas.'}],
                                  'errors': []}, model_spec)

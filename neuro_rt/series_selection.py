"""Pure metadata suggestions and the eligibility decision consumed by future UI.

``resolve_series_ticket`` supplies a SeriesDescriptor or its JSON representation,
optionally with ``metadata`` (DICOM keyword names). No file/path is read here.
Sequence candidates contain role, certainty, evidence (field/signal), conflicts;
evidence records normalized signals rather than copying free-text descriptions.
Acquisition parameters provide uncertain suggestions, never proof of weighting.
T1 without explicit contrast/precontrast evidence suggests both T1 and T1c as
uncertain; POST alone is not contrast evidence (it can mean postoperative).

Capabilities is a trusted snapshot: ``runtimes[id] = {available, reason?}``,
``models[id] = verify_artifacts(...)`` (status ready/missing/corrupt/candidate).
Missing capability reports fail closed. Optional ``series[ticket]`` descriptors
also check identity and known technical failures (geometry.valid/readable=False).
The v2 contract validator remains mandatory before execution, including when
that optional inventory is absent. Uncertainty never requires acceptance.

Host subject_key/study_key must identify subject and acquisition episode; this
module never derives identity or pre/post-operative chronology from file names.
The best single subject/study/modality group is suggested, by coverage, certainty
and lexical identity. Call once per host-selected group to keep its choice.
"""
from collections import defaultdict
from dataclasses import dataclass, field, replace
import copy
import re

from .study_types import ContractMessage, ContractRecord, InputBinding, SeriesDescriptor

ROLES = ('T1', 'T1c', 'T2', 'FLAIR', 'CT')
CERTAINTY = {'unknown': 0, 'uncertain': 1, 'certain': 2}


@dataclass(frozen=True)
class Eligibility(ContractRecord):
    selectable: bool
    missing_roles: list[str] = field(default_factory=list)
    warnings: list[ContractMessage] = field(default_factory=list)
    technical_reasons: list[ContractMessage] = field(default_factory=list)


def _roles(model_spec):
    roles = [channel['role'] for channel in model_spec['channels']]
    if not roles or len(set(roles)) != len(roles) or set(roles) - set(ROLES):
        raise ValueError('Canais de modelo inválidos.')
    return roles


def _descriptor(value):
    if isinstance(value, SeriesDescriptor):
        return copy.deepcopy(value)
    return SeriesDescriptor(**{key: copy.deepcopy(value[key])
                               for key in SeriesDescriptor.__dataclass_fields__ if key in value})


def _classify(metadata, modality):
    if modality == 'CT':
        return [{'role': 'CT', 'certainty': 'certain',
                 'evidence': [{'field': 'Modality', 'signal': 'CT'}], 'conflicts': []}]
    if modality != 'MR':
        return []
    signals = defaultdict(list)
    agent = metadata.get('ContrastBolusAgent')
    agent_present = isinstance(agent, str) and bool(agent.strip())
    contrast = agent_present
    texts = [(name, str(metadata.get(name, '')).upper())
             for name in ('SeriesDescription', 'ProtocolName')]
    contrast = contrast or any(re.search(r'\b(GAD|GADO|CE|T1C|T1CE)\b|T1\s*\+', text)
                               for _, text in texts)
    precontrast = any(re.search(r'\b(PRECONTRAST|NONCONTRAST|NATIVE)\b|SEM\s+CONTRASTE', text)
                      for _, text in texts)
    # A T1 name does not establish whether contrast was given. POST may mean
    # postoperative; PRE may mean preoperative. Only explicit contrast or
    # precontrast evidence narrows roles. Null/nontext agent metadata is unknown.
    t1_roles = (['T1', 'T1c'] if contrast and precontrast else
                ['T1c'] if contrast else ['T1'] if precontrast else ['T1', 'T1c'])
    for name, text in texts:
        if re.search(r'\bFLAIR\b', text):
            signals['FLAIR'].append({'field': name, 'signal': 'FLAIR'})
        # FLAIR often includes T2 in its protocol name; that is not a conflict.
        elif re.search(r'\bT2(?:W)?\b', text):
            signals['T2'].append({'field': name, 'signal': 'T2'})
        if re.search(r'\bT1(?:W|C|CE)?\b', text):
            for role in t1_roles:
                signals[role].append({'field': name, 'signal': 'T1-weighting'})
                if not contrast and not precontrast:
                    signals[role].append({'field': 'contrast-metadata', 'signal': 'contrast-unknown'})
    if contrast and 'T1c' in signals:
        signals['T1c'].append({'field': 'ContrastBolusAgent' if agent_present
                              else 'ProtocolName/SeriesDescription', 'signal': 'contrast-indicated'})
    parameter_only = False
    if not signals:
        try:
            tr, te = float(metadata['RepetitionTime']), float(metadata['EchoTime'])
        except (KeyError, TypeError, ValueError):
            return []
        parameter_roles = t1_roles if 0 < tr < 1000 and 0 < te < 30 else (
            ['T2'] if tr >= 2000 and te >= 60 else [])
        if parameter_roles:
            for role in parameter_roles:
                signals[role] = [{'field': 'RepetitionTime/EchoTime', 'signal': 'weighting-suggestion'}]
                if role in ('T1', 'T1c') and not contrast and not precontrast:
                    signals[role].append({'field': 'contrast-metadata', 'signal': 'contrast-unknown'})
            parameter_only = True
    conflict = list(signals) if len(signals) > 1 else []
    if precontrast and contrast and 'T1c' in signals:
        conflict = sorted(set(conflict) | {'T1', 'T1c'})
        signals['T1c'].append({'field': 'ProtocolName/SeriesDescription', 'signal': 'precontrast-indicated'})
    return [{'role': role, 'certainty': 'uncertain' if parameter_only or conflict else 'certain',
             'evidence': evidence, 'conflicts': [r for r in conflict if r != role]}
            for role, evidence in signals.items()]


def describe_series(series_ticket, host_services) -> SeriesDescriptor:
    """Describe only an authorized host ticket; resolver/geometry errors survive."""
    resolved = host_services.resolve_series_ticket(series_ticket)
    descriptor = _descriptor(resolved)
    if descriptor.ticket != series_ticket:
        raise ValueError('Descritor não corresponde ao ticket autorizado.')
    if not descriptor.subject_key or not descriptor.study_key:
        raise ValueError('Descritor sem identidade de sujeito/momento de aquisição.')
    if descriptor.source_format == 'dicom' and not descriptor.series_uid:
        raise ValueError('Série DICOM sem UID.')
    if isinstance(resolved, dict) and 'metadata' in resolved:
        return replace(descriptor, sequence_candidates=_classify(resolved['metadata'], descriptor.modality))
    return descriptor


def _identity(series):
    return (series.source_format, series.series_uid if series.source_format == 'dicom' else series.ticket)


def _options(series, roles):
    if series.modality == 'CT':
        return {'CT': 'certain'} if roles == ['CT'] else {}
    if series.modality != 'MR':
        return {}
    candidates = {candidate.get('role'): candidate for candidate in series.sequence_candidates
                  if candidate.get('role') in ROLES}
    if candidates:
        return {role: candidates[role].get('certainty', 'uncertain') for role in roles
                if role in candidates}
    # An existing, unclassified MR volume may fill an unresolved MR channel.
    return {role: 'unknown' for role in roles if role != 'CT' and series.modality == 'MR'}


def _rank(assignment, roles):
    return (-len(assignment), -sum(CERTAINTY[c] for _, c in assignment.values()),
            tuple(assignment[r][0].ticket if r in assignment else '\uffff' for r in roles))


def _assign(items, roles):
    # DP over channel subsets: <= 32 states for the five catalog roles. A series
    # is considered once, so ambiguous/unknown inputs cannot be cloned.
    unique = {}
    for item in sorted(items, key=lambda s: (-len(s.sequence_candidates), s.ticket)):
        unique.setdefault(_identity(item), item)
    states = {frozenset(): {}}
    for item in sorted(unique.values(), key=lambda s: s.ticket):
        next_states = dict(states)
        for assigned, mapping in states.items():
            for role, certainty in _options(item, roles).items():
                if role in assigned:
                    continue
                chosen = {**mapping, role: (item, certainty)}
                key = assigned | {role}
                if key not in next_states or _rank(chosen, roles) < _rank(next_states[key], roles):
                    next_states[key] = chosen
        states = next_states
    return min(states.values(), key=lambda a: _rank(a, roles)), list(unique.values())


def suggest_bindings(series_list, model_spec) -> list[InputBinding]:
    roles, groups = _roles(model_spec), defaultdict(list)
    for raw in series_list:
        item = _descriptor(raw)
        if not item.ticket or not item.subject_key or not item.study_key:
            raise ValueError('Série sem ticket/identidade de aquisição.')
        if item.source_format == 'dicom' and not item.series_uid:
            raise ValueError('Série DICOM sem UID.')
        if item.modality != ('CT' if roles == ['CT'] else 'MR'):
            continue
        groups[(item.subject_key, item.study_key, item.modality)].append(item)
    if not groups:
        return []
    choices = [(key, *_assign(items, roles)) for key, items in sorted(groups.items())]
    _, assignment, items = min(choices, key=lambda choice: (_rank(choice[1], roles), choice[0]))
    bindings = []
    assigned_tickets = {chosen.ticket for chosen, _ in assignment.values()}
    for role in roles:
        if role not in assignment:
            continue
        item, certainty = assignment[role]
        warnings = []
        if certainty != 'certain':
            warnings.append(ContractMessage('sequence_uncertain',
                'Série presente com classificação incerta; a associação pode ser alterada.',
                {'role': role, 'certainty': certainty, 'sequence_candidates': item.sequence_candidates}))
        alternatives = sorted(s.ticket for s in items if s.ticket not in assigned_tickets
                              and role in _options(s, roles))
        if alternatives:
            warnings.append(ContractMessage('alternative_series',
                'Há outras séries candidatas; a associação sugerida pode ser trocada.',
                {'role': role, 'alternative_tickets': alternatives}))
        if len(groups) > 1:
            warnings.append(ContractMessage('separate_acquisitions',
                'Sugestão restrita a um único sujeito e momento de aquisição.'))
        bindings.append(InputBinding(role, item.ticket, certainty, 'suggested', warnings))
    return bindings


def evaluate_eligibility(model_spec, bindings, capabilities) -> Eligibility:
    """Return the shared decision; warnings alone never disable a present input."""
    roles, by_role, tickets, warnings, reasons = _roles(model_spec), {}, set(), [], []

    def technical(code, message, **details):
        reasons.append(ContractMessage(code, message, details))

    descriptors = []
    inventory = capabilities.get('series')
    identities = set()
    for binding in bindings:
        if binding.role not in roles:
            technical('unexpected_role', 'Papel não pertence aos canais do modelo.', role=binding.role)
        if binding.role in by_role:
            technical('duplicate_role', 'O modelo repete um papel de entrada.', role=binding.role)
        if binding.series_ticket in tickets:
            technical('duplicate_input', 'Uma série não pode substituir dois canais.')
        if binding.series_ticket:
            by_role[binding.role] = binding
            tickets.add(binding.series_ticket)
        warnings.extend(binding.warnings)
        if binding.certainty != 'certain' and not any(w.code == 'sequence_uncertain' for w in binding.warnings):
            warnings.append(ContractMessage('sequence_uncertain',
                'Série presente com classificação incerta; execução permitida.', {'role': binding.role}))
        if inventory is not None:
            if binding.series_ticket not in inventory:
                technical('unknown_series', 'Ticket não pertence ao inventário autorizado.')
                continue
            item = _descriptor(inventory[binding.series_ticket])
            if item.ticket != binding.series_ticket:
                technical('invalid_series', 'Descritor não corresponde ao ticket.')
            if _identity(item) in identities and binding.series_ticket not in [d.ticket for d in descriptors]:
                technical('duplicate_input', 'Aliases da mesma série não podem substituir dois canais.')
            identities.add(_identity(item))
            descriptors.append(item)
            if item.geometry.get('valid') is False or item.geometry.get('errors'):
                technical('invalid_geometry', 'A série tem falha de geometria declarada pelo leitor.')
            if item.geometry.get('readable') is False:
                technical('unreadable_series', 'O leitor não conseguiu abrir a série.')
    for attribute, code, message in (
            ('subject_key', 'inconsistent_subject', 'Entradas pertencem a sujeitos diferentes.'),
            ('study_key', 'inconsistent_study', 'Entradas pertencem a momentos de aquisição diferentes.'),
            ('modality', 'inconsistent_modality', 'Entradas misturam modalidades incompatíveis.')):
        if len({getattr(d, attribute) for d in descriptors}) > 1:
            technical(code, message)
    if any(d.modality != ('CT' if roles == ['CT'] else 'MR') for d in descriptors):
        technical('inconsistent_modality', 'Modalidade não corresponde aos canais do modelo.')
    if model_spec.get('catalog_state') not in ('distributed', 'verified'):
        technical('model_not_distributed', model_spec.get('availability_reason') or
                  'Modelo candidato ainda não está distribuído para execução.')
    artifact_report = capabilities.get('models', {}).get(model_spec['id'], {})
    if artifact_report.get('status') != 'ready':
        technical('model_artifacts_unavailable', artifact_report.get('reason') or
                  'Pesos/artefatos locais do modelo indisponíveis ou não verificados.',
                  status=artifact_report.get('status', 'unknown'))
    runtime = capabilities.get('runtimes', {}).get(model_spec.get('runtime_id'), {})
    if runtime.get('available') is not True:
        technical('runtime_unavailable', runtime.get('reason') or
                  'Runtime do modelo indisponível nesta instalação.')
    missing = [role for role in roles if role not in by_role]
    return Eligibility(not missing and not reasons, missing, warnings, reasons)

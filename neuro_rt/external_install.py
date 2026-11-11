"""Trusted stdlib SDK for host-owned external maintenance, never local scripts.

The host closes its workers/processes before run_external and reopens afterward.
Only keyword arguments from that host authorize the target and interpreter.
"""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import uuid
import zipfile

from . import install_state
from .plugin_manifest import validate_host_runtime

PLAN_SCHEMA = 'neuro-rt/external-plan/1'
SOURCE_SCHEMA = 'neuro-rt/local-source/1'
TRUSTED_CODE_INVENTORIES = frozenset()  # Injected only by the pinned host bootstrap.
_PLAN_KEYS = {'schema', 'transaction_id', 'mode', 'version', 'source',
              'requires_explicit_trust', 'local_source_accepted', 'action', 'code_only', 'resources_only'}
_ACTIONS = {'install', 'update', 'interrupt_then_update'}
_LOCAL_KEYS = {'folder', 'manifest_sha256', 'code_inventory_sha256', 'file_count', 'total_bytes', 'kind'}
_REMOTE_KEYS = {'release_id', 'asset_id', 'name', 'url', 'size', 'sha256'}


class LocalSourceError(ValueError):
    error_code = 'LOCAL_SOURCE_INVALID'

    def __init__(self, message, source_hint):
        super().__init__(message)
        self.source_hint = source_hint


def _json(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('utf-8')


def _zip_entry(name):
    entry = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry._compresslevel = 1
    entry.external_attr = 0o100644 << 16
    return entry


def code_inventory_sha256(manifest):
    records = [{key: record[key] for key in ('path', 'size', 'sha256')}
               for record in manifest['files'] if record['path'].startswith('code/')]
    return hashlib.sha256(_json(sorted(records, key=lambda record: record['path']))).hexdigest()


def _object(value, allowed, required=None):
    if not isinstance(value, dict) or set(value) - allowed or not (required or allowed).issubset(value):
        raise ValueError('Campos ausentes ou não autorizados no plano externo.')


def inspect_local_source(folder):
    """Authenticate CODE against the host pin; adjacent hashes cannot grant trust."""
    try:
        return _inspect_local_source(folder)
    except LocalSourceError:
        raise
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, RecursionError):
        raise LocalSourceError('A fonte local está incompleta ou não confere. Prepare novamente o bundle autorizado.',
                               'prepare_again') from None


def _inspect_local_source(folder):
    root = install_state._plain(folder).resolve()
    if not install_state._path(root, 'release-manifest.json').is_file() and install_state._path(root, 'programa/release-manifest.json').is_file():
        root = install_state._path(root, 'programa')
    manifest_path = install_state._path(root, 'release-manifest.json')
    if not root.is_dir() or not manifest_path.is_file() or not install_state._path(root, 'code').is_dir():
        raise LocalSourceError('Extraia o SETUP/bundle e selecione a pasta que contém START_HERE.cmd e release-manifest.json.',
                               'extract_setup')
    manifest = install_state._read_json(manifest_path)
    _, total = install_state._manifest_shape(manifest)
    if manifest.get('execution_mode') != 'host':
        raise ValueError('A fonte local deve reutilizar o Python da suíte.')
    inventory_sha = code_inventory_sha256(manifest)
    if inventory_sha not in TRUSTED_CODE_INVENTORIES:
        raise LocalSourceError('Código local não reconhecido por esta suíte. Atualize a suíte ou prepare um SETUP compatível.',
                               'update_suite')
    code = install_state._path(root, 'code')
    expected = {record['path'] for record in manifest['files']}
    for record in manifest['files']:
        path = install_state._path(root, record['path'])
        install_state._verify_file(path, record)
        with path.open('rb') as stream:
            install_state._verify_host_source(stream)
    actual = set()
    for path in code.rglob('*'):
        install_state._plain(path)
        if path.is_file():
            actual.add('code/' + path.relative_to(code).as_posix())
    if actual != expected:
        raise ValueError('Código local contém arquivos não inventariados ou ausentes.')
    install_state._verify_catalog(code, manifest)
    offline = install_state._path(root, 'offline-bundle.json').is_file()
    return {'schema': SOURCE_SCHEMA, 'mode': 'local', 'version': manifest['version'],
            'source_folder': str(root), 'manifest_sha256': install_state._file_digest(manifest_path),
            'code_inventory_sha256': inventory_sha, 'file_count': len(manifest['files']),
            'total_bytes': total, 'trust': 'host-pinned-code', 'requires_explicit_trust': False,
            'kind': 'offline_bundle' if offline else 'setup',
            'resources_verified': False}


def _remote_source(release, version):
    from .plugin_update import GITHUB_API, MAX_SETUP_SIZE, mirror_setup_url
    source = {key: release.get(key) for key in _REMOTE_KEYS}
    install_state._sha(source['sha256'])
    github = (type(source['release_id']) is int and source['release_id'] > 0 and
              type(source['asset_id']) is int and source['asset_id'] > 0 and
              source['url'] == GITHUB_API + '/releases/assets/' + str(source['asset_id']))
    mirror = (source['release_id'] is None and source['asset_id'] is None and
              source['url'] == mirror_setup_url(version))
    if (not (github or mirror) or type(source['size']) is not int
            or not 0 < source['size'] <= MAX_SETUP_SIZE
            or source['name'] != 'NEURO_RT_SETUP_v' + version + '.zip'):
        raise ValueError('Identidade do SETUP externo inválida.')
    return source


def prepare_external_plan(payload, *, source_folder=None):
    """Pin a release or re-inspected local source; does not download or install."""
    if not isinstance(payload, dict):
        raise ValueError('Plano externo deve ser um objeto JSON.')
    action = payload.get('action', 'install')
    code_only = payload.get('code_only', False)
    resources_only = payload.get('resources_only', False)
    if type(code_only) is not bool or type(resources_only) is not bool or code_only and resources_only:
        raise ValueError('Seleção de recursos inválida.')
    if not isinstance(action, str) or action not in _ACTIONS:
        raise ValueError('Ação externa inválida.')
    if source_folder is not None:
        description = inspect_local_source(source_folder)
        if isinstance(payload, dict) and payload.get('schema') == SOURCE_SCHEMA:
            _object(payload, set(description) | {'action', 'code_only', 'resources_only'}, set(description))
            if {key: value for key, value in payload.items() if key not in ('action', 'code_only', 'resources_only')} != description:
                raise ValueError('A fonte local mudou desde a inspeção.')
        else:
            _object(payload, {'mode', 'local_source_accepted', 'action', 'code_only', 'resources_only'}, {'mode', 'local_source_accepted'})
            if payload['mode'] != 'local' or payload['local_source_accepted'] is not True:
                raise ValueError('Confirme a seleção da fonte local antes do preparo.')
        source = {key: description[key] for key in _LOCAL_KEYS - {'folder'}}
        source['folder'] = description['source_folder']
        version = description['version']
        mode = 'local'
    else:
        _object(payload, {'mode', 'release', 'action', 'code_only', 'resources_only'}, {'mode', 'release'})
        release = payload['release']
        if (payload['mode'] != 'online' or not isinstance(release, dict) or
                release.get('state') not in ('available', 'current') or release.get('package_kind') != 'setup'):
            raise ValueError('Selecione um SETUP versionado antes do preparo.')
        version = release.get('version')
        install_state._numeric_version(version)
        source = _remote_source(release, version)
        mode = 'online'
    return {'schema': PLAN_SCHEMA, 'transaction_id': uuid.uuid4().hex,
            'mode': mode, 'version': version, 'source': source,
            'requires_explicit_trust': False, 'local_source_accepted': mode == 'local',
            'action': action, 'code_only': code_only, 'resources_only': resources_only}


def _validate_plan(plan):
    _object(plan, _PLAN_KEYS, _PLAN_KEYS - {'code_only', 'resources_only'})
    if (type(plan.get('code_only', False)) is not bool
            or type(plan.get('resources_only', False)) is not bool
            or plan.get('code_only', False) and plan.get('resources_only', False)):
        raise ValueError('Seleção de recursos inválida.')
    if (plan['schema'] != PLAN_SCHEMA or plan['mode'] not in ('online', 'local') or
            not isinstance(plan['action'], str) or plan['action'] not in _ACTIONS or
            not isinstance(plan['transaction_id'], str) or
            not re.fullmatch('[0-9a-f]{32}', plan['transaction_id']) or
            plan['requires_explicit_trust'] is not False or
            plan['local_source_accepted'] is not (plan['mode'] == 'local')):
        raise ValueError('Plano externo inválido.')
    install_state._numeric_version(plan['version'])
    source = plan['source']
    if plan['mode'] == 'online':
        _object(source, _REMOTE_KEYS)
        _remote_source(source, plan['version'])
    else:
        _object(source, _LOCAL_KEYS)
        if source['kind'] not in ('setup', 'offline_bundle'):
            raise ValueError('Formato da fonte local inválido.')
        if not isinstance(source['folder'], str) or not Path(source['folder']).is_absolute():
            raise ValueError('Pasta local deve ser absoluta.')
        for key in ('manifest_sha256', 'code_inventory_sha256'):
            install_state._sha(source[key])
        if (type(source['file_count']) is not int or not 0 < source['file_count'] <= install_state.MAX_FILES or
                type(source['total_bytes']) is not int or not 0 <= source['total_bytes'] <= install_state.MAX_TOTAL_SIZE):
            raise ValueError('Inventário local inválido.')


def _local_package(plan, destination):
    source = plan['source']
    root = Path(source['folder'])
    description = inspect_local_source(root)
    current = {key: description[key] for key in _LOCAL_KEYS - {'folder'}}
    current['folder'] = description['source_folder']
    if current != source or description['version'] != plan['version']:
        raise ValueError('A fonte local mudou desde a confirmação.')
    manifest = install_state._read_json(install_state._path(root, 'release-manifest.json'))
    # The local launcher/PowerShell is never opened or executed. Only pinned CODE
    # is copied, and each copied byte stream must still match the inspected SHA.
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        archive.writestr(_zip_entry('release-manifest.json'), _json(manifest))
        launcher_bytes = {}
        for record in manifest['files']:
            digest, size = hashlib.sha256(), 0
            launcher = next((name for name, mirror in install_state.SETUP_LAUNCHERS.items()
                             if mirror == record['path']), None)
            with install_state._path(root, record['path']).open('rb') as incoming, \
                    archive.open(_zip_entry(record['path']), 'w', force_zip64=True) as outgoing:
                for block in iter(lambda: incoming.read(1024 * 1024), b''):
                    digest.update(block)
                    size += len(block)
                    outgoing.write(block)
                    if launcher is not None:
                        launcher_bytes.setdefault(launcher, bytearray()).extend(block)
            if size != record['size'] or digest.hexdigest() != record['sha256']:
                raise install_state.InstallFailure('PACKAGE_INTEGRITY', 'A fonte local mudou durante a cópia.')
        for record in manifest.get('launchers', []):
            archive.writestr(_zip_entry(record['path']), launcher_bytes[record['path']])
    return {'path': str(destination), 'sha256': install_state._file_digest(destination)}


def _prepare_resources(recipe, **kwargs):
    from .resource_preparation import prepare_resources
    return prepare_resources(recipe, **kwargs)


def _host_version(root):
    path = install_state._path(root, 'entrega.txt')
    if not path.is_file() or path.stat().st_size > 64 * 1024:
        raise install_state.InstallFailure('HOST_INCOMPATIBLE', 'Versão da base ausente.')
    match = re.search(r'^\s*VERSAO\s*=\s*(\d+(?:\.\d+)*)\s*$',
                      path.read_text(encoding='utf-8-sig'), re.MULTILINE | re.IGNORECASE)
    if not match:
        raise install_state.InstallFailure('HOST_INCOMPATIBLE', 'Versão da base ausente.')
    return match.group(1)


def _resource_only_install(plan, *, plugin, host_python, emit):
    pointer = install_state._path(plugin, 'installation.json')
    previous = install_state._read_json(pointer)
    active_version = previous.get('active_version')
    if previous.get('state') != 'ready' or not active_version or previous.get('pending_version'):
        raise ValueError('Prepare o código da Local Suite antes de instalar os pesos.')
    inventory = install_state._installed_release(plugin, active_version)
    if code_inventory_sha256(inventory) not in TRUSTED_CODE_INVENTORIES:
        raise LocalSourceError('O código ativo não é reconhecido por esta suíte.', 'update_suite')
    code = install_state._path(plugin, 'versions/' + active_version)
    source_folder, bundle_version = None, None
    if plan['mode'] == 'local':
        source = plan['source']
        description = inspect_local_source(source['folder'])
        current = {key: description[key] for key in _LOCAL_KEYS - {'folder'}}
        current['folder'] = description['source_folder']
        if current != source or description['version'] != plan['version']:
            raise ValueError('A fonte local mudou desde a confirmação.')
        if source['kind'] == 'offline_bundle':
            source_folder = Path(description['source_folder'])
            bundle_version = description['version']
    recipe = install_state._read_json(install_state._path(code, 'catalog/resource_recipe.json'))
    labels = {model['id'] for model in recipe['models']} | {wheel['filename'] for wheel in recipe['wheels']}
    labels |= {wheel['name'] for wheel in recipe['wheels'] if isinstance(wheel.get('name'), str)}
    labels |= {spec['filename'] for spec in recipe.get('downloads', {}).values()}
    def progress(event):
        allowed = {'completed_files', 'total_files', 'processed_bytes', 'total_unpacked_bytes',
                   'downloaded_bytes', 'total_bytes'}
        values = {key: value for key, value in event.items()
                  if key in allowed and type(value) is int and value >= 0}
        if event.get('stage') in ('checking', 'preparing', 'downloading', 'extracting', 'validating', 'complete'):
            values['resource_stage'] = event['stage']
        if isinstance(event.get('label'), str) and event['label'] in labels:
            values['component'] = event['label']
        emit('preparing', 'resources', version=active_version, **values)
    emit('preparing', 'resources', version=active_version)
    resources = _prepare_resources(recipe, plugin_root=plugin, host_python=host_python,
                                   source_folder=source_folder, progress=progress)
    from .resource_paths import resolve_resources
    resources, _, _ = resolve_resources(plugin, code, resources)
    if resources is None:
        raise ValueError('Recursos preparados não correspondem ao contrato.')
    if bundle_version is None and (previous.get('resources') or {}).get('recipe_digest') == resources['recipe_digest']:
        bundle_version = previous.get('resource_bundle_version')
    with install_state._installation_lock(plugin) as acquired:
        if not acquired:
            raise install_state.InstallFailure('INSTALL_BUSY', 'Outra transação está em andamento.')
        current = install_state._read_json(pointer)
        if (current.get('state') != 'ready' or current.get('active_version') != active_version
                or current.get('pending_version') or current.get('resources') != previous.get('resources')):
            raise install_state.InstallFailure('INSTALL_BUSY', 'A instalação mudou durante o preparo dos pesos.')
        if code_inventory_sha256(install_state._installed_release(plugin, active_version)) != code_inventory_sha256(inventory):
            raise install_state.InstallFailure('INSTALL_BUSY', 'O código ativo mudou durante o preparo dos pesos.')
        updated = dict(current, resources=resources, resource_bundle_version=bundle_version,
                       resource_recipe_sha256=resources['recipe_digest'],
                       resource_source='offline' if source_folder is not None else 'online')
        install_state._atomic_json(pointer, updated)
    return {'state': 'ready', 'active_version': active_version,
            'resource_bundle_version': bundle_version}


def run_external(plan, progress, *, suite_root, host_python):
    """Prepare resources and activate; host alone owns shutdown/reopen/lifecycle."""
    _validate_plan(plan)
    if progress is not None and not callable(progress):
        raise ValueError('Consumidor de progresso inválido.')
    host = install_state.validate_host_root(suite_root)
    python = validate_host_runtime(host_python)
    version = _host_version(host)
    plugin = install_state._plugin(host)

    def emit(state, stage, *, final=False, **fields):
        event = {'state': state, 'stage': stage, 'version': plan['version'],
                 'transaction_id': plan['transaction_id'], **fields}
        try:
            install_state._atomic_json(plugin / 'external-status.json', event)
        except (OSError, ValueError):
            if not final:
                raise
        if progress is not None:
            try:
                accepted = progress(dict(event))
                if accepted is False and not final:
                    raise install_state.InstallFailure('CANCELLED', 'Cancelado antes da ativação.')
            except BaseException:
                if not final:
                    raise

    committed = False
    result = {'state': 'ready', 'active_version': plan['version']}
    try:
        emit('preparing', 'checking')
        if plan.get('resources_only', False):
            result = _resource_only_install(plan, plugin=plugin, host_python=python, emit=emit)
            committed = True
            emit('ready', 'complete', final=True, version=result['active_version'],
                 active_version=result['active_version'],
                 resource_bundle_version=result['resource_bundle_version'])
            return result
        staging = install_state._path(plugin, 'staging')
        staging.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='external-', dir=staging) as temp:
            target = Path(temp) / 'setup.zip'
            if plan['mode'] == 'local':
                package = _local_package(plan, target)
                source_folder = (Path(plan['source']['folder'])
                                 if plan['source']['kind'] == 'offline_bundle' else None)
            else:
                from .plugin_update import ReleaseClient
                emit('preparing', 'downloading')
                package = ReleaseClient().download(plan['source'], target,
                    progress=lambda copied, total: emit('preparing', 'downloading',
                        downloaded_bytes=copied, total_bytes=total))
                source_folder = None
            from .plugin_update import UpdateCoordinator
            coordinator = UpdateCoordinator(host, host_version=version, host_python=python,
                hold=lambda _: None, busy=lambda: False, cancel=lambda: None, restart=None)
            if plan['mode'] == 'online':
                coordinator._selected = dict(plan['source'], version=plan['version'])
            emit('preparing', 'verifying')
            coordinator.prepare(package, require_host=True, transaction_id=plan['transaction_id'])
            code = install_state._path(plugin, 'versions/' + plan['version'])
            recipe = install_state._read_json(install_state._path(code, 'catalog/resource_recipe.json'))
            labels = {model['id'] for model in recipe['models']} | {wheel['filename'] for wheel in recipe['wheels']}
            labels |= {wheel['name'] for wheel in recipe['wheels'] if isinstance(wheel.get('name'), str)}
            labels |= {spec['filename'] for spec in recipe.get('downloads', {}).values()}
            def resource_progress(event):
                allowed = {'completed_files', 'total_files', 'processed_bytes', 'total_unpacked_bytes',
                           'downloaded_bytes', 'total_bytes'}
                values = {key: value for key, value in event.items()
                          if key in allowed and type(value) is int and value >= 0}
                stage, label = event.get('stage'), event.get('label')
                if isinstance(stage, str) and stage in {'checking', 'preparing', 'downloading', 'extracting', 'validating', 'complete'}:
                    values['resource_stage'] = stage
                if isinstance(label, str) and label in labels:
                    values['component'] = label
                emit('preparing', 'resources', **values)
            from .resource_paths import resolve_resources

            resources = None
            if plan.get('code_only', False):
                current = install_state._read_json(plugin / 'installation.json')
                if current.get('resources') is not None:
                    try:
                        resources, _, _ = resolve_resources(plugin, code, current['resources'])
                    except ValueError:
                        pass
            else:
                emit('preparing', 'resources')
                resources = _prepare_resources(recipe, plugin_root=plugin, host_python=python,
                                               source_folder=source_folder, progress=resource_progress)
                if not isinstance(resources, dict) or resources.get('schema') != 'neuro-rt/resolved-resources/1':
                    raise ValueError('Recursos preparados não correspondem ao contrato.')
                resources, _, _ = resolve_resources(plugin, code, resources)
            with install_state._installation_lock(plugin) as acquired:
                if not acquired:
                    raise install_state.InstallFailure('INSTALL_BUSY', 'Outra transação está em andamento.')
                state = install_state._read_json(plugin / 'installation.json')
                if state.get('transaction_id') != plan['transaction_id'] or state.get('pending_version') != plan['version']:
                    raise install_state.InstallFailure('INSTALL_BUSY', 'A versão pendente mudou.')
                state['pending_resources'] = resources
                if not plan.get('code_only', False):
                    bundle_version = (plan['version'] if plan['mode'] == 'local'
                        and plan['source']['kind'] == 'offline_bundle' else None)
                    if bundle_version is None and (state.get('resources') or {}).get('recipe_digest') == resources['recipe_digest']:
                        bundle_version = state.get('resource_bundle_version')
                    state['resource_bundle_version'] = bundle_version
                    state['resource_recipe_sha256'] = resources['recipe_digest']
                    state['resource_source'] = ('offline' if state['resource_bundle_version'] else 'online')
                install_state._atomic_json(plugin / 'installation.json', state)
            emit('activating', 'validating')
            try:
                install_state.activate_release(plugin, plan['version'], host_python=python)
                committed = True
            except BaseException:
                with install_state._installation_lock(plugin) as acquired:
                    if not acquired:
                        raise install_state.InstallFailure('INSTALL_BUSY', 'Rollback aguarda outra transação.')
                    current = install_state._read_json(plugin / 'installation.json')
                    if current.get('transaction_id') != plan['transaction_id']:
                        raise install_state.InstallFailure('INSTALL_BUSY', 'A transação mudou durante a ativação.')
                    install_state._atomic_json(plugin / 'installation.json', state)
                committed = False
                raise
        emit('ready', 'complete', final=True, active_version=plan['version'])
        return result
    except BaseException as error:
        if committed:
            emit('ready', 'complete', final=True, active_version=plan['version'])
            return result
        diagnostic = install_state.sanitize_install_error(error, 'preparing')
        try:
            emit('failed', diagnostic['error_stage'], final=True, **diagnostic)
        except OSError:
            pass
        raise

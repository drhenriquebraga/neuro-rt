"""Guided setup: open host maintenance or assemble a transportable local bundle."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from . import install_state
from .external_install import inspect_local_source, _json
from .plugin_manifest import validate_host_runtime
from .resource_paths import resolve_resources


def _prepare_resources(recipe, **kwargs):
    from .resource_preparation import prepare_resources
    return prepare_resources(recipe, **kwargs)


def _prepare_offline_archives(recipe, **kwargs):
    from .resource_preparation import prepare_offline_archives
    return prepare_offline_archives(recipe, **kwargs)


def _resource_cache_path(root, spec):
    from .resource_preparation import resource_cache_path
    return resource_cache_path(root, spec)


def _preparation_policy():
    from .plugin_consent import policy
    return policy()


def _require_preparation_terms(terms):
    policy = _preparation_policy()
    if (not isinstance(terms, dict) or terms.get('accepted') is not True or
            terms.get('version') != policy['version'] or terms.get('digest') != policy['digest']):
        raise ValueError('Leia e aceite o termo atual antes de preparar o pacote offline.')


def _copy_verified(source_root, relative, target_root, target_relative, record, progress=None):
    source = install_state._path(source_root, relative)
    target = install_state._path(target_root, target_relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    digest, size = hashlib.sha256(), 0
    with source.open('rb') as incoming, target.open('xb') as outgoing:
        for block in iter(lambda: incoming.read(1024 * 1024), b''):
            digest.update(block)
            size += len(block)
            outgoing.write(block)
            if progress is not None:
                progress(size)
    if size != record['size'] or digest.hexdigest() != record['sha256']:
        raise install_state.InstallFailure('PACKAGE_INTEGRITY', 'Recurso alterado durante a cópia local.')


def build_local_bundle(output_folder, *, source_folder, cache_root, host_python,
                       progress=None, inspector=None, terms=None):
    """Export exactly verified CODE, model files and missing extras; never Python."""
    _require_preparation_terms(terms)  # Preparation only: never records installation/first use.
    inspect = inspector or inspect_local_source
    source = install_state._plain(source_folder).resolve()
    description = inspect(source)
    output = install_state._plain(output_folder).resolve()
    cache = install_state._plain(cache_root).resolve()
    if (output.exists() or output == source or source.is_relative_to(output) or cache.is_relative_to(output)
            or output.is_relative_to(source / 'code') or cache.is_relative_to(source / 'code')):
        raise ValueError('Escolha uma nova pasta vazia para o bundle local.')
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = install_state._read_json(install_state._path(source, 'release-manifest.json'))
    recipe = install_state._read_json(install_state._path(source, 'code/catalog/resource_recipe.json'))
    def emit(stage, **values):
        if progress is not None and progress(dict(state='preparing', stage=stage, **values)) is False:
            raise install_state.InstallFailure('CANCELLED', 'Montagem local cancelada.')
    emit('checking')
    labels = {model['id'] for model in recipe['models']} | {wheel['filename'] for wheel in recipe['wheels']}
    labels |= {wheel['name'] for wheel in recipe['wheels'] if isinstance(wheel.get('name'), str)}
    labels |= {spec['filename'] for spec in recipe.get('downloads', {}).values()}
    def resource_progress(event):
        values = {key: event[key] for key in ('downloaded_bytes', 'total_bytes', 'completed_files',
                  'total_files', 'processed_bytes', 'total_unpacked_bytes')
                  if type(event.get(key)) is int and event[key] >= 0}
        if isinstance(event.get('stage'), str) and event['stage'] in {'checking', 'preparing', 'downloading', 'extracting', 'validating', 'complete'}:
            values['resource_stage'] = event['stage']
        if isinstance(event.get('label'), str) and event['label'] in labels:
            values['component'] = event['label']
        emit('resources', **values)
    resources = _prepare_resources(recipe, plugin_root=cache, host_python=host_python,
                                   progress=resource_progress)
    resources, _, receipt_path = resolve_resources(cache, source / 'code', resources)
    archives = _prepare_offline_archives(recipe, plugin_root=cache, progress=resource_progress)
    raw_manifest = _json(manifest)
    planned = list(manifest['files']) + list(manifest.get('launchers', [])) + list(archives)
    planned.append({'size': len(raw_manifest)})
    for model in recipe['models']:
        planned.extend(model['files'].values())
        if 'provenance.json' not in model['files']:
            planned.append({'size': len(_json(model.get('provenance', {})))})
    total_files, total_bytes = len(planned), sum(record['size'] for record in planned)
    copied_bytes = 0
    inventory = []
    categories = {key: {'files': 0, 'bytes': 0} for key in ('code', 'models', 'wheels', 'notices', 'launchers', 'metadata')}
    def record_file(name, record, category):
        nonlocal copied_bytes
        inventory.append(dict(path=name, size=record['size'], sha256=record['sha256'], category=category))
        categories[category]['files'] += 1
        categories[category]['bytes'] += record['size']
        copied_bytes += record['size']
        emit('copying', completed_files=len(inventory), total_files=total_files,
             processed_bytes=copied_bytes, total_unpacked_bytes=total_bytes, component=category)
    def copy(source_root, relative, stage, target_relative, record, category):
        _copy_verified(source_root, relative, stage, target_relative, record,
            progress=lambda count: emit('copying', completed_files=len(inventory), total_files=total_files,
                processed_bytes=copied_bytes + count, total_unpacked_bytes=total_bytes, component=category))
        record_file(target_relative, record, category)
    with tempfile.TemporaryDirectory(prefix='.neuro-offline-', dir=output.parent) as temp:
        stage = Path(temp) / 'bundle'
        stage.mkdir()
        for record in manifest['files']:
            copy(source, record['path'], stage, record['path'], record, 'code')
        for record in manifest.get('launchers', []):
            copy(source, install_state.SETUP_LAUNCHERS[record['path']], stage, record['path'], record, 'launchers')
        (stage / 'release-manifest.json').write_bytes(raw_manifest)
        record_file('release-manifest.json', {'size': len(raw_manifest), 'sha256': hashlib.sha256(raw_manifest).hexdigest()}, 'metadata')
        for model in recipe['models']:
            relative = resources['model_relative_paths'][model['id']]
            for name, record in model['files'].items():
                copy(cache, relative + '/' + name, stage, relative + '/' + name, record, 'models')
            if 'provenance.json' not in model['files']:
                raw = _json(model.get('provenance', {}))
                name = relative + '/provenance.json'
                install_state._path(stage, name).write_bytes(raw)
                record_file(name, {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}, 'models')
        # Keep original archives for extras so an offline target can unpack its
        # own missing delta. Original model files above make model archives redundant.
        for spec in archives:
            original = _resource_cache_path(cache, spec)
            relative = 'downloads/' + spec['sha256'] + '/' + spec['filename']
            copy(cache, original.relative_to(cache).as_posix(), stage, relative, spec,
                 'wheels' if spec['filename'].lower().endswith('.whl') else 'notices')
        (stage / 'offline-bundle.json').write_bytes(_json({
            'schema': 'neuro-rt/local-bundle/1', 'version': description['version'],
            'code_inventory_sha256': description['code_inventory_sha256'], 'recipe_digest': resources['recipe_digest'],
            'resources_resolved_for_target': False, 'python_included': False,
            'categories': categories, 'files': sorted(inventory, key=lambda record: record['path']),
            'payload_bytes': sum(value['bytes'] for value in categories.values()),
            'receipt_excludes_itself': True}))
        inspect(stage)  # Trust still comes from the host pin, not offline-bundle.json.
        emit('complete')
        install_state._replace(stage, output)
    return {'state': 'ready', 'version': description['version'], 'folder': str(output)}


def _host_file(root, filename):
    for relative in ('app/' + filename, filename):
        path = install_state._path(root, relative)
        if path.is_file():
            return path
    raise install_state.InstallFailure('HOST_INCOMPATIBLE', 'Atualize a Local Suite para 8.12 ou posterior.')


def open_host_settings(suite_root, *, host_python):
    root = install_state._plain(suite_root).resolve()
    entry = _host_file(root, 'radai_plugin_setup.py')
    python = install_state._plain(host_python).resolve()
    if python != Path(sys.executable).resolve():
        raise ValueError('O assistente deve usar o mesmo Python da suíte.')
    return subprocess.run([str(python), '-I', '-B', str(entry), '--open-settings', '--suite-root', str(root)]).returncode


def _host_inspector(root):
    path = _host_file(root, 'radai_neuro_install.py')
    spec = importlib.util.spec_from_file_location('_neuro_setup_trusted_host', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.inspect_local_source


def _description():
    code = Path(__file__).resolve().parents[1]
    metadata = install_state._read_json(install_state._path(code, 'module.json'))
    documents = []
    paths = [code / 'LICENSE', code / 'NOTICE']
    paths.extend(sorted((code / 'licenses').rglob('*')))
    for path in paths:
        install_state._plain(path)
        if (path.is_file() and path.stat().st_size <= 2 * 1024 * 1024 and
                (path.name in ('LICENSE', 'NOTICE') or path.suffix.lower() in ('.txt', '.md', '.html'))):
            documents.append(path.name + '\n\n' + path.read_text(encoding='utf-8-sig'))
    return {'state': 'ready', 'version': metadata['version'],
            'policy': _preparation_policy(), 'licenses': '\n\n'.join(documents)}


def _progress_reporter(progress_file=None, cancel_file=None, *, quiet=False):
    destination = install_state._plain(progress_file).absolute() if progress_file else None
    cancel = install_state._plain(cancel_file).absolute() if cancel_file else None
    last_phase, last_time = None, 0.0
    labels = {'checking': 'Conferindo o pacote…', 'resources': 'Preparando os recursos necessários…',
              'copying': 'Copiando os arquivos verificados…', 'complete': 'Concluindo o pacote…'}
    def report(event):
        nonlocal last_phase, last_time
        final = event.get('state') in ('ready', 'failed', 'settings_opened')
        if not final and cancel is not None and cancel.exists():
            return False
        safe = {key: value for key, value in event.items() if key in ('state', 'stage', 'version',
                'resource_stage', 'component', 'reason', 'error_code', 'error_stage', 'source_hint')
                and isinstance(value, str) and len(value) <= 600}
        for key in ('downloaded_bytes', 'total_bytes', 'completed_files', 'total_files', 'processed_bytes', 'total_unpacked_bytes'):
            if type(event.get(key)) is int and event[key] >= 0:
                safe[key] = event[key]
        phase = (safe.get('state'), safe.get('stage'), safe.get('resource_stage'), safe.get('component'))
        now = time.monotonic()
        if not final and phase == last_phase and now - last_time < .25:
            return True
        previous = last_phase
        last_phase, last_time = phase, now
        if destination is not None:
            try:
                install_state._atomic_json(destination, safe)
            except (OSError, ValueError):
                if not final:
                    raise
        if not quiet and phase != previous:
            print(labels.get(safe.get('stage'), 'Preparando…'))
        return True
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite-root', required=True)
    parser.add_argument('--mode', choices=('prepare', 'offline'))
    parser.add_argument('--output')
    parser.add_argument('--describe', action='store_true')
    parser.add_argument('--accept-preparation-terms', action='store_true')
    parser.add_argument('--preparation-policy-version')
    parser.add_argument('--preparation-policy-sha256')
    parser.add_argument('--progress-file')
    parser.add_argument('--cancel-file')
    args = parser.parse_args(argv)
    report = _progress_reporter(args.progress_file, args.cancel_file, quiet=bool(args.progress_file or args.describe))
    try:
        root = install_state.validate_host_root(args.suite_root)
        validate_host_runtime(sys.executable)
        if args.describe:
            print(json.dumps(_description(), ensure_ascii=True))
            return 0
        mode = args.mode
        if not args.progress_file:
            print('NEURO RT — assistente de preparação')
            print('Usando o Python já instalado na Local Suite; nenhum Python ou venv será baixado.')
        if mode is None:
            print('1. Preparar/atualizar o plugin na Local Suite existente')
            print('2. Montar um bundle offline LOCAL para transportar')
            choice = input('Escolha 1 ou 2: ').strip()
            mode = {'1': 'prepare', '2': 'offline'}.get(choice)
            if mode is None:
                raise ValueError('Seleção inválida.')
        if mode == 'prepare':
            code = open_host_settings(root, host_python=sys.executable)
            if code:
                raise install_state.InstallFailure('HOST_INCOMPATIBLE', 'A suíte não abriu as configurações.')
            result = {'state': 'settings_opened', 'stage': 'complete'}
            report(result)
            print(json.dumps(result, ensure_ascii=True))
            return 0
        policy = _preparation_policy()
        accepted = args.accept_preparation_terms
        if not accepted:
            print(policy['title'] + ' — ' + policy['version'])
            for clause in policy['clauses']:
                print('\n' + clause['text'])
            print('\nPreparar o pacote não instala o plugin nem registra aceite de instalação ou primeiro uso.')
            accepted = input('Digite ACEITO para preparar os recursos: ').strip() == 'ACEITO'
        terms = {'accepted': accepted, 'version': args.preparation_policy_version or policy['version'],
                 'digest': args.preparation_policy_sha256 or policy['digest']}
        _require_preparation_terms(terms)
        destination = args.output or input('Pasta NOVA onde guardar o bundle offline: ').strip().strip('"')
        if not destination:
            raise ValueError('Selecione uma pasta de destino.')
        output = Path(destination).absolute()
        source = Path(__file__).resolve().parents[2]
        result = build_local_bundle(output, source_folder=source,
            cache_root=output.parent / '.neuro-rt-resources', host_python=sys.executable,
            inspector=_host_inspector(root), progress=report, terms=terms)
        report(dict(result, stage='complete'))
        if not args.progress_file:
            print('Bundle local pronto. Na outra Local Suite, abra Configurações > NEURO RT e escolha essa pasta.')
        print(json.dumps(result, ensure_ascii=True))
        return 0 if result['state'] == 'ready' else 1
    except (Exception, KeyboardInterrupt) as error:
        diagnostic = install_state.sanitize_install_error(error, 'preparing')
        hint = getattr(error, 'source_hint', None)
        if hint in ('extract_setup', 'update_suite', 'prepare_again'):
            diagnostic['source_hint'] = hint
            diagnostic['reason'] = {'extract_setup': 'Extraia o SETUP/bundle e escolha a pasta com START_HERE.cmd e release-manifest.json.',
                'update_suite': 'Atualize a Local Suite para usar este SETUP ou escolha um SETUP compatível.',
                'prepare_again': 'A fonte local não confere. Prepare novamente o pacote autorizado.'}[hint]
        result = dict(diagnostic, state='failed', stage='preparing')
        report(result)
        if not args.progress_file and not args.describe:
            print(diagnostic['reason'])
            print('Se a rede bloquear recursos, prepare o bundle em outra máquina com a Local Suite completa e escolha a pasta na suíte de destino.')
        print(json.dumps(result, ensure_ascii=True))
        return 1


if __name__ == '__main__':
    sys.exit(main())

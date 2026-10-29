"""Transactional offline plugin installation using only the Python standard library.

The caller supplies a locally authorized ZIP and an externally obtained SHA256;
this module never downloads, invokes pip, imports or executes packaged code.
Activation is called by the host's coordinated reopen flow, never by install.
See installer/PACKAGE_FORMAT.md for the complete release-package/1 contract.
"""
import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import stat
import sys
import time
import uuid
import zipfile

from .plugin_manifest import _numeric_version, _relative_path, read_manifest
from .model_registry import load_catalog

SCHEMA = 'neuro-rt/release-package/1'
MAX_MANIFEST = 16 * 1024 * 1024
MAX_FILES = 100_000
MAX_FILE_SIZE = 16 * 1024 ** 3
MAX_TOTAL_SIZE = 64 * 1024 ** 3
MAX_COMPRESSION_RATIO = 1000
SPACE_MARGIN = 16 * 1024 * 1024
CODE_ROOTS = {'module.json', 'neuro_rt', 'web', 'integration', 'app', 'catalog',
              'licenses', 'LICENSE', 'NOTICE', 'requirements.txt', 'models.lock.json'}


@dataclass(frozen=True)
class InstallStatus:
    transaction_id: str | None = None
    state: str = 'absent'
    stage: str = 'idle'
    downloaded_bytes: int = 0
    total_bytes: int = 0
    reason: str = ''


@dataclass(frozen=True)
class InstallReceipt:
    transaction_id: str | None
    version: str | None
    verified_artifacts: tuple
    activation_pending: bool
    following: bool = False


@dataclass(frozen=True)
class ActivationReceipt:
    previous_version: str | None
    active_version: str
    restart_required: bool
    status: str


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value):
        raise ValueError('Identificador inválido.')
    return value


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('SHA256 externo/fixado obrigatório, hexadecimal minúsculo.')
    return value


def _plain(path):
    """Reject all links/reparse points, even those resolving within the boundary."""
    path = Path(path).absolute()
    for current in (path, *path.parents):
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Links, junctions e reparse points não são permitidos na instalação.')
    return path


def _validate_name(name):
    """Validate package spelling only; never consult cwd or any filesystem."""
    if not isinstance(name, str) or '\\' in name:
        raise ValueError('Caminho de pacote deve usar separadores / relativos.')
    parts = name.split('/')
    windows = PureWindowsPath(name)
    if (not name or windows.drive or windows.root or
            any(part in ('', '.', '..') or part.endswith((' ', '.')) for part in parts) or
            any(ord(char) < 32 or char in '<>:"|?*' for char in name)):
        raise ValueError('Caminho do pacote deve ser relativo, contido e sem aliases Windows.')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {
        f'{prefix}{number}' for prefix in ('COM', 'LPT') for number in range(1, 10)}
    if any(part.split('.')[0].upper() in reserved for part in parts):
        raise ValueError('Caminho contém nome reservado do Windows.')
    return name


def _path(root, name):
    _validate_name(name)
    _plain(root)
    target = _relative_path(root, name)
    _plain(Path(root).joinpath(*name.split('/')))
    return target


def validate_host_root(host_root):
    """Recognize the actual flat bundle or source checkout, without guessing paths."""
    root = _plain(host_root).resolve()
    bundled = all((root / name).is_file() for name in ('radai_panel.py', 'radai_ui.py', 'entrega.txt'))
    source = all((root / name).is_file() for name in ('app/radai_panel.py', 'app/radai_ui.py', 'tools/_componentes.py'))
    if not root.is_dir() or not (bundled or source):
        raise ValueError('SuiteRoot não contém os marcadores reais do Local Suite.')
    for name in (('radai_panel.py', 'radai_ui.py', 'entrega.txt') if bundled else
                 ('app/radai_panel.py', 'app/radai_ui.py', 'tools/_componentes.py')):
        _plain(root / name)
    return root


def _plugin(host):
    root = _path(host, 'Plugins/NEURO RT')
    for name in ('versions', 'runtimes', 'models', 'data', 'config', 'staging',
                 'transactions', 'installation.json', 'install-status.json', '.install.lock'):
        _path(root, name)
    return root


def _read_json(path):
    _plain(path)
    if Path(path).stat().st_size > MAX_MANIFEST:
        raise ValueError('Manifesto/estado excede o limite de tamanho.')
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _atomic_json(path, values):
    path = _plain(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(values, stream, ensure_ascii=True, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        _plain(path)
        _replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _replace(source, target):
    # Antivirus/indexers can briefly hold Windows files without delete sharing.
    for attempt in range(10):
        _plain(target)
        try:
            os.replace(source, target)
            return
        except PermissionError as error:
            if getattr(error, 'winerror', None) not in (5, 32, 33) or attempt == 9:
                raise
            time.sleep(0.05 * (attempt + 1))


@contextmanager
def _installation_lock(root):
    """A kernel lock survives stale lock files and releases on process death."""
    root = _plain(root)
    root.mkdir(parents=True, exist_ok=True)
    file = _path(root, '.install.lock')
    acquired = False
    with file.open('a+b') as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            pass
        try:
            yield acquired
        finally:
            if acquired:
                stream.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _status(root, transaction, state, stage, total=0, downloaded=0, reason=''):
    value = asdict(InstallStatus(transaction, state, stage, downloaded, total, reason))
    _atomic_json(_path(root, 'install-status.json'), value)
    _atomic_json(_path(root, f'transactions/{transaction}/status.json'), value)


def _copy_stream(source, destination, progress=None):
    copied = 0
    for chunk in iter(lambda: source.read(1024 * 1024), b''):
        destination.write(chunk)
        copied += len(chunk)
        if progress:
            progress(copied)
    return copied


def _file_digest(path):
    _plain(path)
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_file(path, record):
    path = _plain(path)
    if not path.is_file() or path.stat().st_size != record['size'] or _file_digest(path) != record['sha256']:
        raise ValueError('Arquivo ausente ou corrompido; identidade SHA256 não confere.')


def _manifest_shape(data):
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or data.get('plugin_id') != 'neuro-rt':
        raise ValueError('Manifesto de release inválido.')
    _numeric_version(data.get('version'))
    files = data.get('files')
    if not isinstance(files, list) or not files or len(files) > MAX_FILES:
        raise ValueError('Inventário de arquivos inválido.')
    seen = set()
    total = 0
    for record in files:
        if not isinstance(record, dict):
            raise ValueError('Registro de arquivo inválido.')
        name = record.get('path')
        _validate_name(name)
        if name.casefold() in seen:
            raise ValueError('Caminhos duplicados ou aliases de caixa no pacote.')
        seen.add(name.casefold())
        parts = name.split('/')
        if parts[0] == 'code':
            if len(parts) < 2 or parts[1] not in CODE_ROOTS:
                raise ValueError('Payload de código contém diretório privado/não autorizado.')
        elif parts[0] not in ('models', 'runtimes') or len(parts) < 4:
            raise ValueError('Payload deve separar code, runtimes e models.')
        if type(record.get('size')) is not int or not 0 <= record['size'] <= MAX_FILE_SIZE:
            raise ValueError('Tamanho de arquivo inválido.')
        _sha(record.get('sha256'))
        total += record['size']
    if total > MAX_TOTAL_SIZE:
        raise ValueError('Payload excede o limite de extração.')
    components = [('code', None)]
    runtimes = data.get('runtimes')
    if not isinstance(runtimes, list) or not runtimes:
        raise ValueError('Release deve fixar runtimes completos.')
    runtime_keys = set()
    for runtime in runtimes:
        key = (_identifier(runtime.get('id')), _sha(runtime.get('lock_digest')))
        if key in runtime_keys:
            raise ValueError('Runtime duplicado.')
        runtime_keys.add(key)
        prefix = f'runtimes/{key[0]}/{key[1]}'
        _validate_name(runtime.get('python'))
        components.append((prefix, runtime))
    selected = data.get('runtime')
    if not isinstance(selected, dict) or not any(
            all(selected.get(k) == runtime.get(k) for k in ('id', 'lock_digest', 'python')) for runtime in runtimes):
        raise ValueError('Runtime principal não pertence aos runtimes fixados.')
    models = data.get('models')
    if not isinstance(models, list):
        raise ValueError('Lista de modelos inválida.')
    model_keys = set()
    for model in models:
        key = (_identifier(model.get('id')), _identifier(model.get('revision')))
        if key in model_keys:
            raise ValueError('Modelo/revisão duplicado.')
        model_keys.add(key)
        components.append((f'models/{key[0]}/{key[1]}', model))
    names = {record['path'] for record in files}
    for prefix, component in components:
        records = [name for name in names if name.startswith(prefix + '/')]
        if not records:
            raise ValueError('Componente sem inventário completo.')
        licenses = data.get('code_license_paths') if component is None else component.get('license_paths')
        if not isinstance(licenses, list) or not licenses:
            raise ValueError('Componente sem textos de licença fixados.')
        for license_path in licenses:
            _validate_name(license_path)
            if prefix + '/' + license_path not in names:
                raise ValueError('Licença não pertence ao inventário.')
        if prefix.startswith('runtimes/') and prefix + '/' + component['python'] not in names:
            raise ValueError('Python do runtime não está fixado no inventário.')
    if any(not any(name.startswith(prefix + '/') for prefix, _ in components) for name in names):
        raise ValueError('Arquivo fora dos componentes declarados.')
    if 'code/module.json' not in names:
        raise ValueError('Manifesto do plugin ausente.')
    return components, total


def _inspect_zip(zipped):
    entries = zipped.infolist()
    if len(entries) > MAX_FILES + 1:
        raise ValueError('ZIP excede o limite de entradas.')
    names = set()
    files = {}
    total = 0
    for entry in entries:
        # Explicit directory entries have no payload and are unnecessary.
        name = entry.filename
        _validate_name(name.rstrip('/') if entry.is_dir() else name)
        if name.casefold().rstrip('/') in names:
            raise ValueError('Entradas ZIP duplicadas ou aliases de caixa.')
        names.add(name.casefold().rstrip('/'))
        mode = entry.external_attr >> 16
        if (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR) or
                entry.flag_bits & 1 or entry.external_attr & 0x400):
            raise ValueError('ZIP contém link, reparse point ou entrada criptografada.')
        if (entry.file_size > MAX_FILE_SIZE or
                entry.file_size > max(entry.compress_size, 1) * MAX_COMPRESSION_RATIO):
            raise ValueError('ZIP excede o limite de tamanho/compressão segura.')
        total += entry.file_size
        if total > MAX_TOTAL_SIZE:
            raise ValueError('ZIP excede o limite total de extração.')
        if not entry.is_dir():
            files[name] = entry
    if 'release-manifest.json' not in files or files['release-manifest.json'].file_size > MAX_MANIFEST:
        raise ValueError('ZIP não contém release-manifest.json válido.')
    data = json.loads(zipped.read('release-manifest.json').decode('utf-8'))
    components, size = _manifest_shape(data)
    records = {record['path']: record for record in data['files']}
    if any(name != 'release-manifest.json' and name not in records for name in files):
        raise ValueError('ZIP contém arquivo não fixado no manifesto.')
    for name, entry in files.items():
        if name != 'release-manifest.json' and entry.file_size != records[name]['size']:
            raise ValueError('Tamanho ZIP difere do inventário.')
    for name in records:
        if name.startswith('code/') and name not in files:
            raise ValueError('Código precisa estar completo dentro do ZIP.')
    return data, components, size, files


def _verify_component(base, prefix, data, exact=True):
    records = [r for r in data['files'] if r['path'].startswith(prefix + '/')]
    expected = set()
    for record in records:
        relative = record['path'][len(prefix) + 1:]
        expected.add(relative)
        _verify_file(_path(base, relative), record)
    if exact:
        actual = set()
        for path in Path(base).rglob('*'):
            _plain(path)
            if path.is_file():
                actual.add(path.relative_to(base).as_posix())
        # Receipts are generated by this installer, never supplied in code payload.
        if prefix == 'code':
            actual -= {'release-manifest.json', 'install-receipt.json'}
        if actual != expected:
            raise ValueError('Componente contém arquivos não inventariados.')


def _verify_catalog(code, data):
    manifest = read_manifest(code / 'module.json')
    if manifest.version != data['version']:
        raise ValueError('Versão do plugin difere da release.')
    names = {r['path']: r for r in data['files']}
    if 'code/' + manifest.catalog not in names or 'code/' + manifest.adapter.split(':')[0] not in names:
        raise ValueError('Catálogo/adaptador não está fixado no payload.')
    runtimes = {r['id']: r for r in data['runtimes']}
    if set(manifest.runtimes) != set(runtimes):
        raise ValueError('Runtimes do plugin e release diferem.')
    for runtime_id, runtime in manifest.runtimes.items():
        if runtime['python'] != runtimes[runtime_id]['python']:
            raise ValueError('Entrypoint Python difere do runtime fixado.')
    for model in load_catalog(_path(code, manifest.catalog)):
        if model['catalog_state'] == 'candidate':
            continue
        if model.get('host_managed') is True:
            if (model['id'] != 'cranio_buti' or model.get('runtime_id') != 'host-nnunet'
                    or model.get('adapter_id') != 'buti_host'):
                raise ValueError('Componente gerenciado pelo host fora do contrato autorizado.')
            # Optional host capability: no Neuro-owned weights/runtime are claimed.
            continue
        key = (model['id'], model['revision'])
        if not any((m['id'], m['revision']) == key for m in data['models']):
            raise ValueError('Modelo distribuído sem pesos completos na release.')
        if model.get('runtime_id') not in runtimes:
            raise ValueError('Modelo distribuído sem runtime completo na release.')
        for artifact in model['artifacts']:
            _validate_name(artifact.get('path'))
            record = names.get(f'models/{key[0]}/{key[1]}/' + artifact['path'])
            if record is None or record['sha256'] != artifact.get('sha256') or (
                    artifact.get('size') is not None and artifact['size'] != record['size']):
                raise ValueError('Artefato distribuído não corresponde ao SHA256 do catálogo.')


def _installed_release(root, version):
    _numeric_version(version)
    code = _path(root, f'versions/{version}')
    data = _read_json(_path(code, 'release-manifest.json'))
    components, _ = _manifest_shape(data)
    if data['version'] != version:
        raise ValueError('Versão instalada diverge do inventário.')
    for prefix, _ in components:
        _verify_component(code if prefix == 'code' else _path(root, prefix), prefix, data)
    _verify_catalog(code, data)
    return data


def read_install_status(plugin_root) -> InstallStatus:
    root = _plain(plugin_root)
    if not root.exists():
        return InstallStatus()
    status_file = _path(root, 'install-status.json')
    state_file = _path(root, 'installation.json')
    value = _read_json(status_file) if status_file.exists() else asdict(InstallStatus())
    if state_file.exists():
        installation = _read_json(state_file)
        # A failed update is reported by status while the old active pointer survives.
        if value['state'] not in ('installing', 'updating', 'checking', 'failed'):
            value['state'] = installation['state']
        if value['state'] == 'ready':
            try:
                _installed_release(root, installation.get('active_version'))
            except (ValueError, OSError, KeyError, TypeError):
                value.update(state='failed', stage='integrity', reason='Instalação ativa incompleta ou corrompida.')
    elif value['state'] == 'ready':
        value.update(state='failed', stage='integrity', reason='Recibo da instalação ativa ausente.')
    return InstallStatus(**{key: value.get(key, default) for key, default in asdict(InstallStatus()).items()})


def begin_install(host_root, package, transaction_id) -> InstallReceipt:
    """Install a local {'path': ZIP, 'sha256': external digest} without activation.

    A simultaneous caller receives following=True and polls read_install_status.
    Repeating a successful transaction returns its original durable receipt.
    Failed/interrupted IDs may retry only the same package identity.
    """
    transaction_id = _identifier(transaction_id)
    if not isinstance(package, dict) or not isinstance(package.get('path'), (str, os.PathLike)):
        raise ValueError('Pacote offline requer path e SHA256 externo obrigatório.')
    expected = _sha(package.get('sha256'))
    host = validate_host_root(host_root)
    root = _plugin(host)
    source = _plain(package['path']).resolve()
    if not source.is_file():
        raise ValueError('Pacote offline não encontrado.')
    with _installation_lock(root) as acquired:
        if not acquired:
            current = read_install_status(root)
            return InstallReceipt(current.transaction_id, None, (), False, True)
        transaction = _path(root, f'transactions/{transaction_id}')
        identity = _path(transaction, 'identity.json')
        receipt_file = _path(transaction, 'receipt.json')
        if identity.exists() and _read_json(identity).get('sha256') != expected:
            raise ValueError('ID de transação já pertence a outro pacote.')
        if receipt_file.exists():
            values = _read_json(receipt_file)
            _installed_release(root, values['version'])
            values['verified_artifacts'] = tuple(values['verified_artifacts'])
            return InstallReceipt(**values)
        _atomic_json(identity, {'sha256': expected})
        state_file = _path(root, 'installation.json')
        previous = _read_json(state_file) if state_file.exists() else {
            'schema': 'neuro-rt/installation/1', 'state': 'absent', 'active_version': None,
            'previous_version': None, 'pending_version': None, 'runtime': None}
        state = 'updating' if previous.get('active_version') else 'installing'
        promoted = []
        stage = _path(root, f'staging/{transaction_id}')
        committed = False
        total = source.stat().st_size
        try:
            _status(root, transaction_id, state, 'checking', total)
            if shutil.disk_usage(root).free < total + SPACE_MARGIN:
                raise ValueError('Sem espaço livre suficiente para staging do pacote.')
            # The transaction owns only this directory; never remove persistent data.
            if stage.exists():
                _safe_remove_tree(stage, root / 'staging')
            stage.mkdir(parents=True)
            archive = _path(stage, 'package.zip')
            with source.open('rb') as incoming, archive.open('xb') as outgoing:
                _copy_stream(incoming, outgoing, lambda count: _status(
                    root, transaction_id, state, 'copying', total, count))
                outgoing.flush()
                os.fsync(outgoing.fileno())
            if archive.stat().st_size != total or _file_digest(archive) != expected:
                raise ValueError('SHA256 do pacote não corresponde ao hash externo autorizado.')
            _status(root, transaction_id, state, 'verifying', total, total)
            with zipfile.ZipFile(archive) as zipped:
                data, components, size, entries = _inspect_zip(zipped)
                if shutil.disk_usage(root).free < size + SPACE_MARGIN:
                    raise ValueError('Sem espaço livre para extração e coexistência da versão anterior.')
                version = data['version']
                code_destination = _path(root, f'versions/{version}')
                # A published version is immutable and may only be installed identically.
                if code_destination.exists():
                    old = _read_json(_path(code_destination, 'release-manifest.json'))
                    _manifest_shape(old)
                    _verify_component(code_destination, 'code', old)
                    if old != data:
                        raise ValueError('Versão existente possui outra identidade; publique nova versão.')
                payload = _path(stage, 'payload')
                payload.mkdir()
                for prefix, _ in components:
                    destination = code_destination if prefix == 'code' else _path(root, prefix)
                    if destination.exists():
                        _verify_component(destination, prefix, data)
                        continue
                    for record in (r for r in data['files'] if r['path'].startswith(prefix + '/')):
                        if record['path'] not in entries:
                            raise ValueError('Payload omitido sem componente íntegro para reutilização.')
                        target = _path(payload, record['path'])
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with zipped.open(entries[record['path']]) as incoming, target.open('xb') as outgoing:
                            _copy_stream(incoming, outgoing)
                        _verify_file(target, record)
                code = code_destination if code_destination.exists() else payload / 'code'
                _verify_catalog(code, data)
                receipt = InstallReceipt(transaction_id, version,
                    tuple(r['path'] for r in data['files']), True)
                if not code_destination.exists():
                    _atomic_json(code / 'release-manifest.json', data)
                    _atomic_json(code / 'install-receipt.json', dict(asdict(receipt), package_sha256=expected,
                        licenses={'code': data['code_license_paths'], 'runtimes': data['runtimes'], 'models': data['models']}))
                _status(root, transaction_id, state, 'publishing', total, total)
                for prefix, _ in components:
                    destination = code_destination if prefix == 'code' else _path(root, prefix)
                    if destination.exists():
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    _plain(destination)
                    _replace(_path(payload, prefix), destination)
                    promoted.append(destination)
                _installed_release(root, version)
                for name in ('data', 'config'):
                    _path(root, name).mkdir(exist_ok=True)
                updated = dict(previous, state='installed_pending_restart', pending_version=version,
                               transaction_id=transaction_id, pending_runtime=data['runtime'], package_sha256=expected)
                _atomic_json(state_file, updated)
                committed = True
                _atomic_json(receipt_file, asdict(receipt))
                _status(root, transaction_id, 'installed_pending_restart', 'complete', total, total)
            _safe_remove_tree(stage, root / 'staging')
            return receipt
        except BaseException as error:
            if not committed:
                for destination in reversed(promoted):
                    _safe_remove_tree(destination, root)
            # Avoid exposing source paths, exception text, PHI or filesystem details.
            try:
                _status(root, transaction_id, 'failed', 'cancelled' if isinstance(error, KeyboardInterrupt) else 'failed',
                        total, reason='Instalação cancelada.' if isinstance(error, KeyboardInterrupt) else
                        'Instalação interrompida; versão ativa e dados preservados.')
            except OSError:
                pass
            raise


def _safe_remove_tree(path, boundary):
    path, boundary = _plain(path).resolve(), _plain(boundary).resolve()
    if path == boundary or not path.is_relative_to(boundary):
        raise ValueError('Limpeza fora do staging/componente autorizado.')
    for item in path.rglob('*'):
        _plain(item)
    shutil.rmtree(path)


def activate_release(plugin_root, version) -> ActivationReceipt:
    """Atomically select an installed release after host coordination/reopen.

    Previous verified versions remain available for explicit rollback. Call before
    mounting a service; restart_required=False means the coordinated startup may
    continue, never that imported modules were hot swapped.
    """
    _numeric_version(version)
    root = _plain(plugin_root).resolve()
    with _installation_lock(root) as acquired:
        if not acquired:
            raise ValueError('Instalação ocupada; acompanhe o status da transação.')
        data = _installed_release(root, version)
        state_file = _path(root, 'installation.json')
        previous = _read_json(state_file)
        old = previous.get('active_version')
        receipt = ActivationReceipt(old if old != version else previous.get('previous_version'), version, False, 'ready')
        updated = dict(previous, state='ready', active_version=version,
                       previous_version=receipt.previous_version, pending_version=None,
                       pending_runtime=None, runtime=data['runtime'])
        _atomic_json(state_file, updated)
        transaction = previous.get('transaction_id', 'activation')
        _status(root, transaction, 'ready', 'active')
        return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite-root', required=True)
    parser.add_argument('--package-path', required=True)
    parser.add_argument('--package-sha256', required=True)
    parser.add_argument('--transaction-id', required=True)
    args = parser.parse_args(argv)
    try:
        receipt = begin_install(args.suite_root, {'path': args.package_path, 'sha256': args.package_sha256}, args.transaction_id)
        print(json.dumps(asdict(receipt)))
        return 0
    except (ValueError, OSError, zipfile.BadZipFile, KeyError, TypeError):
        print(json.dumps({'state': 'failed', 'reason': 'Pacote inválido ou instalação não pôde ser concluída.'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())

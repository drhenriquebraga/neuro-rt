"""Transactional offline plugin installation using only the Python standard library.

The caller supplies a locally authorized ZIP and an externally obtained SHA256;
this module never downloads, invokes pip, imports or executes packaged code.
Activation is called by the host's coordinated reopen flow, never by install.
See installer/PACKAGE_FORMAT.md for the complete release-package/1 contract.
"""
import argparse
import codecs
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import errno
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

from .plugin_manifest import (_numeric_version, _relative_path, read_manifest,
                              validate_host_runtime, HostRuntimeUnavailable)
from .model_registry import load_catalog

SCHEMA = 'neuro-rt/release-package/1'
MAX_MANIFEST = 16 * 1024 * 1024
MAX_FILES = 100_000
MAX_FILE_SIZE = 16 * 1024 ** 3
MAX_TOTAL_SIZE = 64 * 1024 ** 3
MAX_COMPRESSION_RATIO = 1000
SPACE_MARGIN = 16 * 1024 * 1024
CODE_ROOTS = {'module.json', 'neuro_rt', 'web', 'integration', 'app', 'catalog',
              'licenses', 'LICENSE', 'NOTICE', 'requirements.txt', 'models.lock.json', 'installer'}
HOST_CODE_SUFFIXES = {
    'neuro_rt': {'.py'}, 'integration': {'.py'}, 'app': {'.py'},
    'web': {'.html', '.js', '.css', '.svg', '.json'}, 'catalog': {'.json'},
    'licenses': {'.txt', '.md', '.html'}, 'installer': {'.ps1'},
}


@dataclass(frozen=True)
class InstallStatus:
    transaction_id: str | None = None
    state: str = 'absent'
    stage: str = 'idle'
    downloaded_bytes: int = 0
    total_bytes: int = 0
    reason: str = ''
    completed_files: int = 0
    total_files: int = 0
    processed_bytes: int = 0
    total_unpacked_bytes: int = 0
    error_code: str = ''
    error_stage: str = ''
    os_errno: int | None = None
    winerror: int | None = None
    cleanup_pending: bool = False
    cleanup_error_code: str = ''
    rollback_cleanup_pending: bool = False


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


def _status(root, transaction, state, stage, total=0, downloaded=0, reason='', **details):
    value = asdict(InstallStatus(transaction, state, stage, downloaded, total, reason, **details))
    _atomic_json(_path(root, 'install-status.json'), value)
    _atomic_json(_path(root, f'transactions/{transaction}/status.json'), value)


class InstallFailure(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.error_code = code


_ERROR_REASONS = {
    'HOST_INCOMPATIBLE': 'Atualize ou repare a base do Local Suite antes de instalar o plugin.',
    'INSTALL_BUSY': 'Outra preparação do plugin está em andamento. Aguarde sua conclusão antes de tentar novamente.',
    'INSUFFICIENT_SPACE': 'Espaço livre insuficiente para preparar o NEURO RT.',
    'PACKAGE_INTEGRITY': 'A integridade do pacote ou de um componente não confere. Baixe novamente o pacote autorizado.',
    'PACKAGE_INVALID': 'O pacote não corresponde ao formato ou inventário autorizado.',
    'PERMISSION_DENIED': 'O Windows não permitiu gravar na pasta do plugin. Confira as permissões da instalação.',
    'FILE_BUSY': 'Um arquivo do plugin está em uso. Aguarde a liberação e tente novamente.',
    'PATH_TOO_LONG': 'O Windows recusou um caminho longo da instalação.',
    'IO_ERROR': 'O Windows não concluiu a leitura ou gravação dos arquivos da instalação.',
    'CANCELLED': 'Instalação cancelada; versão ativa e dados preservados.',
    'INSTALL_FAILED': 'A instalação foi interrompida; versão ativa e dados preservados.',
}
_ERROR_STAGES = frozenset(('checking', 'copying', 'verifying', 'extracting', 'validating',
    'publishing', 'complete', 'cleaning', 'preparing', 'downloading', 'activation',
    'restarting', 'waiting', 'host_validation', 'restart'))


def sanitize_install_error(error, stage):
    """Return controlled diagnostics; exception arguments and paths are never used."""
    number = getattr(error, 'errno', None)
    number = number if type(number) is int else None
    windows = getattr(error, 'winerror', None)
    windows = windows if type(windows) is int else None
    code = error.error_code if isinstance(error, (InstallFailure, HostRuntimeUnavailable)) else None
    if code not in _ERROR_REASONS:
        if isinstance(error, KeyboardInterrupt):
            code = 'CANCELLED'
        elif number == errno.ENOSPC or windows == 112:
            code = 'INSUFFICIENT_SPACE'
        elif windows in (32, 33):
            code = 'FILE_BUSY'
        elif isinstance(error, PermissionError) or number in (errno.EACCES, errno.EPERM) or windows == 5:
            code = 'PERMISSION_DENIED'
        elif number == errno.ENAMETOOLONG or windows == 206:
            code = 'PATH_TOO_LONG'
        elif isinstance(error, OSError):
            code = 'IO_ERROR'
        elif isinstance(error, (ValueError, KeyError, TypeError, zipfile.BadZipFile)):
            code = 'PACKAGE_INVALID'
        else:
            code = 'INSTALL_FAILED'
    return {'reason': _ERROR_REASONS[code], 'error_code': code,
            'error_stage': stage if isinstance(stage, str) and stage in _ERROR_STAGES else 'unknown',
            'os_errno': number, 'winerror': windows}


class _InstallProgress:
    def __init__(self, root, transaction, state, total):
        self.root, self.transaction, self.state = root, transaction, state
        self.stage, self._published_stage, self._last_write = 'checking', None, None
        self.total, self.downloaded = total, 0
        self._verified_bytes = 0
        self.values = {'completed_files': 0, 'total_files': 0, 'processed_bytes': 0,
                       'total_unpacked_bytes': 0}

    def publish(self, stage=None, force=False, **changes):
        if stage is not None:
            self.stage = stage
        if 'downloaded_bytes' in changes:
            self.downloaded = max(self.downloaded, changes.pop('downloaded_bytes'))
        for name in ('completed_files', 'processed_bytes'):
            if name in changes:
                changes[name] = max(self.values[name], changes[name])
        self.values.update(changes)
        now = time.monotonic()
        if (force or self.stage != self._published_stage or self._last_write is None
                or now - self._last_write >= .25):
            _status(self.root, self.transaction, self.state, self.stage, self.total,
                    self.downloaded, **self.values)
            self._published_stage, self._last_write = self.stage, now

    def verified(self, size):
        self._verified_bytes += size
        self.publish(completed_files=self.values['completed_files'] + 1,
                     processed_bytes=self._verified_bytes)


def _cleanup_staging(root, transaction):
    """Only delete a known transaction's staging; journal retries under the lock."""
    transaction = _identifier(transaction)
    pending, code = False, ''
    try:
        stage = _path(root, 'staging/' + transaction)
        if stage.exists():
            _safe_remove_tree(stage, root / 'staging')
    except (OSError, ValueError) as error:
        pending, code = True, sanitize_install_error(error, 'cleaning')['error_code']
    try:
        _atomic_json(_path(root, 'transactions/' + transaction + '/cleanup.json'), {
            'schema': 'neuro-rt/staging-cleanup/1', 'transaction_id': transaction,
            'pending': pending, 'error_code': code})
    except (OSError, ValueError) as error:
        pending, code = True, sanitize_install_error(error, 'cleaning')['error_code']
    return pending, code


def _retry_staging_cleanup(root):
    pending, code = False, ''
    folder = _path(root, 'transactions')
    if not folder.exists():
        return pending, code
    for directory in folder.iterdir():
        try:
            _plain(directory)
            if not directory.is_dir():
                continue
            transaction = _identifier(directory.name)
            identity = _path(root, 'transactions/' + transaction + '/identity.json')
            if not identity.is_file():
                continue
            _sha(_read_json(identity).get('sha256'))
            marker = _path(root, 'transactions/' + transaction + '/cleanup.json')
            record = _read_json(marker) if marker.exists() else None
            if record is not None and (record.get('schema') != 'neuro-rt/staging-cleanup/1'
                    or record.get('transaction_id') != transaction or type(record.get('pending')) is not bool):
                raise ValueError('Registro de limpeza inválido.')
            if _path(root, 'staging/' + transaction).exists() or (record or {}).get('pending'):
                remains, error_code = _cleanup_staging(root, transaction)
                pending = pending or remains
                code = code or error_code
        except (OSError, ValueError, KeyError, TypeError) as error:
            pending, code = True, code or sanitize_install_error(error, 'cleaning')['error_code']
    return pending, code


def _refresh_cleanup_status(root, pending, code, verified_version=None):
    try:
        file = _path(root, 'install-status.json')
        if not file.exists():
            return
        value = _read_json(file)
        original = dict(value)
        rollback = value.get('rollback_cleanup_pending') is True
        value.update(cleanup_pending=pending or rollback,
                     cleanup_error_code=code or (value.get('cleanup_error_code', '') if rollback else ''))
        if verified_version is not None:
            state = _read_json(_path(root, 'installation.json'))
            if state.get('pending_version') == verified_version:
                value.update(state='installed_pending_restart', stage='complete', reason='',
                             error_code='', error_stage='', os_errno=None, winerror=None)
        if value == original:
            return
        _atomic_json(file, value)
        transaction = value.get('transaction_id')
        if transaction is not None:
            _identifier(transaction)
            _atomic_json(_path(root, 'transactions/' + transaction + '/status.json'), value)
    except (OSError, ValueError, KeyError, TypeError):
        pass


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
    path = Path(path)
    if not path.is_file() or path.stat().st_size != record['size'] or _file_digest(path) != record['sha256']:
        raise InstallFailure('PACKAGE_INTEGRITY', 'Arquivo ausente ou corrompido; identidade SHA256 não confere.')


def _manifest_shape(data):
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or data.get('plugin_id') != 'neuro-rt':
        raise ValueError('Manifesto de release inválido.')
    _numeric_version(data.get('version'))
    execution_mode = data.get('execution_mode', 'isolated')
    if execution_mode not in ('isolated', 'host'):
        raise ValueError('Modo de execução da release inválido.')
    if execution_mode == 'host' and any(
            key in data for key in ('host_python', 'python_executable', 'worker_python')):
        raise ValueError('O pacote não pode fornecer o binding do Python da suíte.')
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
            if execution_mode == 'host' and (
                    (parts[1] in HOST_CODE_SUFFIXES and (len(parts) < 3 or
                     Path(parts[-1]).suffix.lower() not in HOST_CODE_SUFFIXES[parts[1]])) or
                    (parts[1] not in HOST_CODE_SUFFIXES and len(parts) != 2)):
                raise ValueError('Modo host permite somente código, instaladores e textos autorizados.')
        elif parts[0] not in ('models', 'runtimes') or len(parts) < 4:
            raise ValueError('Payload deve separar code, runtimes e models.')
        if execution_mode == 'host' and parts[0] != 'code':
            raise ValueError('Modo host não distribui runtimes, bibliotecas ou pesos.')
        if type(record.get('size')) is not int or not 0 <= record['size'] <= MAX_FILE_SIZE:
            raise ValueError('Tamanho de arquivo inválido.')
        _sha(record.get('sha256'))
        total += record['size']
    if total > MAX_TOTAL_SIZE:
        raise ValueError('Payload excede o limite de extração.')
    components = [('code', None)]
    runtimes = data.get('runtimes')
    if execution_mode == 'host' and (
            'runtime' not in data or data['runtime'] is not None or runtimes != [] or data.get('models') != []):
        raise ValueError('Modo host deve usar apenas o Python da suíte, sem componentes científicos.')
    if not isinstance(runtimes, list) or (not runtimes and execution_mode != 'host'):
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
    if execution_mode != 'host' and (not isinstance(selected, dict) or not any(
            all(selected.get(k) == runtime.get(k) for k in ('id', 'lock_digest', 'python')) for runtime in runtimes)):
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


def _verify_host_source(stream):
    """Host CODE is UTF-8 text, never a renamed executable, wheel or weight."""
    decoder = codecs.getincrementaldecoder('utf-8-sig')()
    try:
        for block in iter(lambda: stream.read(64 * 1024), b''):
            text = decoder.decode(block)
            if any(ord(char) < 32 and char not in '\t\r\n' for char in text):
                raise ValueError('Payload binário não é permitido no código do modo host.')
        decoder.decode(b'', final=True)
    except UnicodeError as error:
        raise ValueError('Modo host permite somente fontes e textos UTF-8.') from error


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
    if data.get('execution_mode', 'isolated') == 'host':
        for name in records:
            with zipped.open(files[name]) as stream:
                _verify_host_source(stream)
    return data, components, size, files


def _verify_component(base, prefix, data, exact=True, progress=None):
    records = [r for r in data['files'] if r['path'].startswith(prefix + '/')]
    expected = set()
    for record in records:
        relative = record['path'][len(prefix) + 1:]
        expected.add(relative)
        _verify_file(_path(base, relative), record)
        if progress:
            progress(record['size'])
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
    if manifest.execution_mode != data.get('execution_mode', 'isolated'):
        raise ValueError('Modo de execução do plugin difere da release.')
    models = load_catalog(_path(code, manifest.catalog))
    if manifest.execution_mode == 'host':
        if manifest.enabled_tools != ('nidus',):
            raise ValueError('Modo host desta entrega permite somente Nidus RT.')
        # Future specifications remain validated documentation, not installed models.
        return
    runtimes = {r['id']: r for r in data['runtimes']}
    if set(manifest.runtimes) != set(runtimes):
        raise ValueError('Runtimes do plugin e release diferem.')
    for runtime_id, runtime in manifest.runtimes.items():
        if runtime['python'] != runtimes[runtime_id]['python']:
            raise ValueError('Entrypoint Python difere do runtime fixado.')
    for model in models:
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


def _installed_release(root, version, progress=None):
    _numeric_version(version)
    code = _path(root, f'versions/{version}')
    data = _read_json(_path(code, 'release-manifest.json'))
    components, _ = _manifest_shape(data)
    if data['version'] != version:
        raise ValueError('Versão instalada diverge do inventário.')
    for prefix, _ in components:
        _verify_component(code if prefix == 'code' else _path(root, prefix), prefix, data, progress=progress)
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


def begin_install(host_root, package, transaction_id, *, host_python=None) -> InstallReceipt:
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
        cleanup_pending, cleanup_code = _retry_staging_cleanup(root)
        _refresh_cleanup_status(root, cleanup_pending, cleanup_code)
        if receipt_file.exists():
            values = _read_json(receipt_file)
            installed = _installed_release(root, values['version'])
            if installed.get('execution_mode', 'isolated') == 'host':
                validate_host_runtime(host_python)
            _refresh_cleanup_status(root, cleanup_pending, cleanup_code, verified_version=values['version'])
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
        progress = _InstallProgress(root, transaction_id, state, total)
        progress.values.update(cleanup_pending=cleanup_pending, cleanup_error_code=cleanup_code)
        try:
            progress.publish('checking', force=True)
            if shutil.disk_usage(root).free < total + SPACE_MARGIN:
                raise InstallFailure('INSUFFICIENT_SPACE', 'Sem espaço livre suficiente para staging do pacote.')
            # The transaction owns only this directory; never remove persistent data.
            if stage.exists():
                _safe_remove_tree(stage, root / 'staging')
            stage.mkdir(parents=True)
            archive = _path(stage, 'package.zip')
            with source.open('rb') as incoming, archive.open('xb') as outgoing:
                progress.publish('copying')
                _copy_stream(incoming, outgoing, lambda count: progress.publish(downloaded_bytes=count))
                outgoing.flush()
                os.fsync(outgoing.fileno())
            progress.publish('verifying', force=True, downloaded_bytes=total)
            if archive.stat().st_size != total or _file_digest(archive) != expected:
                raise InstallFailure('PACKAGE_INTEGRITY', 'SHA256 do pacote não corresponde ao hash externo autorizado.')
            with zipfile.ZipFile(archive) as zipped:
                data, components, size, entries = _inspect_zip(zipped)
                if data.get('execution_mode', 'isolated') == 'host':
                    validate_host_runtime(host_python)
                progress.publish(force=True, total_files=len(data['files']), total_unpacked_bytes=size)
                if shutil.disk_usage(root).free < size + SPACE_MARGIN:
                    raise InstallFailure('INSUFFICIENT_SPACE', 'Sem espaço livre para extração e coexistência da versão anterior.')
                version = data['version']
                code_destination = _path(root, f'versions/{version}')
                # A published version is immutable and may only be installed identically.
                if code_destination.exists():
                    progress.publish('validating')
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
                        progress.publish('validating')
                        _verify_component(destination, prefix, data, progress=progress.verified)
                        continue
                    progress.publish('extracting')
                    for record in (r for r in data['files'] if r['path'].startswith(prefix + '/')):
                        if record['path'] not in entries:
                            raise ValueError('Payload omitido sem componente íntegro para reutilização.')
                        target = _path(payload, record['path'])
                        target.parent.mkdir(parents=True, exist_ok=True)
                        processed_before = progress._verified_bytes
                        with zipped.open(entries[record['path']]) as incoming, target.open('xb') as outgoing:
                            _copy_stream(incoming, outgoing, lambda copied: progress.publish(
                                processed_bytes=processed_before + copied))
                        _verify_file(target, record)
                        progress.verified(record['size'])
                code = code_destination if code_destination.exists() else payload / 'code'
                progress.publish('validating', force=True)
                _verify_catalog(code, data)
                receipt = InstallReceipt(transaction_id, version,
                    tuple(r['path'] for r in data['files']), True)
                if not code_destination.exists():
                    _atomic_json(code / 'release-manifest.json', data)
                    _atomic_json(code / 'install-receipt.json', dict(asdict(receipt), package_sha256=expected,
                        licenses={'code': data['code_license_paths'], 'runtimes': data['runtimes'], 'models': data['models']}))
                progress.publish('publishing', force=True)
                for prefix, _ in components:
                    destination = code_destination if prefix == 'code' else _path(root, prefix)
                    if destination.exists():
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    _plain(destination)
                    _replace(_path(payload, prefix), destination)
                    promoted.append(destination)
                _installed_release(root, version, progress=lambda _: progress.publish())
                for name in ('data', 'config'):
                    _path(root, name).mkdir(exist_ok=True)
                updated = dict(previous, state='installed_pending_restart', pending_version=version,
                               transaction_id=transaction_id, pending_runtime=data['runtime'],
                               pending_execution_mode=data.get('execution_mode', 'isolated'), package_sha256=expected)
                _atomic_json(state_file, updated)
                committed = True
                _atomic_json(receipt_file, asdict(receipt))
                progress.state = 'installed_pending_restart'
                progress.publish('complete', force=True)
            pending, code = _cleanup_staging(root, transaction_id)
            progress.publish('complete', force=True, cleanup_pending=cleanup_pending or pending,
                             cleanup_error_code=cleanup_code or code)
            return receipt
        except BaseException as error:
            if committed:
                pending, code = _cleanup_staging(root, transaction_id)
                try:
                    progress.state = 'installed_pending_restart'
                    progress.publish('complete', force=True, cleanup_pending=True,
                                     cleanup_error_code=code or sanitize_install_error(error, 'cleaning')['error_code'],
                                     error_code='', error_stage='', os_errno=None, winerror=None)
                except (OSError, ValueError):
                    pass
                if isinstance(error, Exception):
                    return receipt
                raise
            rollback_pending = False
            for destination in reversed(promoted):
                try:
                    _safe_remove_tree(destination, root)
                except (OSError, ValueError):
                    rollback_pending = True
            pending, code = _cleanup_staging(root, transaction_id)
            try:
                diagnostic = sanitize_install_error(error, progress.stage)
                progress.state = 'failed'
                progress.publish('cancelled' if isinstance(error, KeyboardInterrupt) else 'failed',
                                 force=True, cleanup_pending=cleanup_pending or pending or rollback_pending,
                                 cleanup_error_code=cleanup_code or code,
                                 rollback_cleanup_pending=rollback_pending, **diagnostic)
            except OSError:
                pass
            raise


def _safe_remove_tree(path, boundary):
    path, boundary = _plain(path).resolve(), _plain(boundary).resolve()
    if path == boundary or not path.is_relative_to(boundary):
        raise ValueError('Limpeza fora do staging/componente autorizado.')
    for item in path.rglob('*'):
        _plain(item)
    def retry_readonly(function, name, exception):
        error = exception[1]
        candidate = _plain(name).resolve()
        if candidate != path and not candidate.is_relative_to(path):
            raise ValueError('Limpeza fora da árvore autorizada.') from error
        info = candidate.lstat()
        if (os.name != 'nt' or not isinstance(error, PermissionError)
                or function not in (os.unlink, os.remove, os.rmdir)
                or not getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_READONLY):
            raise error
        os.chmod(candidate, info.st_mode | stat.S_IWRITE)
        _plain(candidate)
        function(candidate)
    shutil.rmtree(path, onerror=retry_readonly)


def activate_release(plugin_root, version, *, host_python=None) -> ActivationReceipt:
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
        if data.get('execution_mode', 'isolated') == 'host':
            validate_host_runtime(host_python)
        state_file = _path(root, 'installation.json')
        previous = _read_json(state_file)
        old = previous.get('active_version')
        receipt = ActivationReceipt(old if old != version else previous.get('previous_version'), version, False, 'ready')
        updated = dict(previous, state='ready', active_version=version,
                       previous_version=receipt.previous_version, pending_version=None,
                       pending_runtime=None, runtime=data['runtime'], pending_execution_mode=None,
                       execution_mode=data.get('execution_mode', 'isolated'))
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
        from . import plugin_consent
        if not plugin_consent.accepted(plugin_consent.config_for_suite(args.suite_root), 'installation'):
            raise ValueError('Aceite do termo do plugin ausente.')
        receipt = begin_install(args.suite_root, {'path': args.package_path, 'sha256': args.package_sha256},
                                args.transaction_id, host_python=sys.executable)
        print(json.dumps(asdict(receipt)))
        return 0
    except (ValueError, OSError, zipfile.BadZipFile, KeyError, TypeError):
        print(json.dumps({'state': 'failed', 'reason': 'Pacote inválido ou instalação não pôde ser concluída.'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())

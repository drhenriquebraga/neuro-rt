"""Standard-library bootstrap, also shipped with the Local Suite host.

This module must work when no Neuro runtime or package is installed. The host
copy is radai_plugins.py; installation and inference remain plugin-owned.
"""
import hashlib
import importlib.util
import json
import re
import stat
import sys
import threading
from pathlib import Path, PureWindowsPath

PLUGIN_ID = 'neuro-rt'
HOST_CONTRACT = 'local-suite/plugins/1'
_MOUNT_LOCK = threading.RLock()


def _inside(root, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError('Caminho relativo inválido.')
    win = PureWindowsPath(relative)
    parts = relative.replace('\\', '/').split('/')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {p + str(n) for p in ('COM', 'LPT') for n in range(1, 10)}
    if (win.drive or win.root or any(p in ('', '.', '..') or p.endswith((' ', '.'))
            or p.split('.')[0].upper() in reserved for p in parts)
            or any(ord(c) < 32 or c in '<>:"|?*' for c in relative)):
        raise ValueError('Caminho fora do contrato de instalação.')
    root = Path(root).absolute()
    raw_path = root.joinpath(*parts)
    for parent in (raw_path, *raw_path.parents):
        try:
            info = parent.lstat()
        except FileNotFoundError:
            pass
        else:
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('A instalação do plugin não permite links ou redirecionamentos.')
        if parent == root:
            break
    path = raw_path.resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Caminho escapa da instalação.')
    return path


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+(?:\.\d+)*', value):
        raise ValueError('Versão inválida.')
    parts = [int(n) for n in value.split('.')]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def _json(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('Metadados de instalação inválidos.')
    return value


def discover_plugin(suite_root, plugin_id=PLUGIN_ID, host_info=None):
    result = {'plugin_id': PLUGIN_ID, 'state': 'absent', 'reason': '', 'active_version': None}
    try:
        if plugin_id != PLUGIN_ID:
            raise ValueError('Plugin não autorizado.')
        plugin = _inside(suite_root, 'Plugins/NEURO RT')
        result['plugin_root'] = str(plugin)
        state_file = plugin / 'installation.json'
        if not state_file.is_file():
            return result
        state = _json(state_file)
        if state.get('schema') != 'neuro-rt/installation/1':
            raise ValueError('Schema de instalação inválido.')
        result['state'] = state.get('state', 'failed')
        result['installation_state'] = state
        if result['state'] != 'ready':
            result['reason'] = 'Instalação aguardando preparo ou ativação.'
            return result
        version = state.get('active_version')
        _version(version)
        code = _inside(plugin, 'versions/' + version)
        manifest = _json(code / 'module.json')
        if (manifest.get('schema') != 'neuro-rt/plugin-manifest/1'
                or manifest.get('id') != PLUGIN_ID or manifest.get('version') != version
                or manifest.get('host_contract') != HOST_CONTRACT):
            raise ValueError('Manifesto não corresponde à instalação.')
        minimum = manifest.get('host_min_version')
        host_info = host_info or {}
        if (minimum is None or host_info.get('contract') != HOST_CONTRACT
                or _version(host_info.get('version')) < _version(minimum)):
            result.update(state='incompatible', reason='Atualize o Local Suite para a versão exigida pelo plugin.')
            return result
        inventory = _json(code / 'release-manifest.json')
        if (inventory.get('schema') != 'neuro-rt/release-package/1'
                or inventory.get('plugin_id') != PLUGIN_ID or inventory.get('version') != version):
            raise ValueError('Inventário da release não corresponde ao plugin.')
        files = inventory.get('files')
        if not isinstance(files, list) or not files:
            raise ValueError('Inventário de código ausente.')
        covered = set()
        for entry in files:
            name = entry.get('path')
            if not isinstance(name, str):
                raise ValueError('Entrada de inventário inválida.')
            if name.startswith('code/'):
                relative = name[5:]
                file = _inside(code, relative)
                if relative in covered:
                    raise ValueError('Inventário repete arquivo.')
                covered.add(relative)
            elif name.startswith(('models/', 'runtimes/')):
                file = _inside(plugin, name)
            else:
                raise ValueError('Artefato fora das áreas do plugin.')
            digest = entry.get('sha256')
            if (not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)
                    or type(entry.get('size')) is not int or not file.is_file()
                    or file.stat().st_size != entry['size']):
                raise ValueError('Artefato da instalação incompleto ou inválido.')
            sha = hashlib.sha256()
            with file.open('rb') as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b''):
                    sha.update(block)
            if sha.hexdigest() != digest:
                raise ValueError('Integridade de artefato não confirmada.')
        adapter = manifest.get('adapter', '')
        if not isinstance(adapter, str) or adapter.count(':') != 1:
            raise ValueError('Adaptador inválido.')
        adapter_file, function = adapter.split(':')
        _inside(code, adapter_file)
        if (adapter_file not in covered or 'module.json' not in covered
                or not re.fullmatch('[A-Za-z_]\\w*', function)):
            raise ValueError('Adaptador não protegido pelo inventário.')
        allowed_receipts = {'release-manifest.json', 'install-receipt.json'}
        actual = set()
        for file in code.rglob('*'):
            relative = file.relative_to(code).as_posix()
            _inside(code, relative)
            if '__pycache__' in file.parts or file.suffix.lower() in ('.pyc', '.pyo'):
                raise ValueError('Bytecode não é permitido no código instalado do plugin.')
            if file.is_file():
                actual.add(relative)
        if actual - allowed_receipts != covered:
            raise ValueError('A instalação contém arquivos não previstos no inventário.')
        result.update(state='ready', reason='', active_version=version,
                      code_dir=str(code), manifest=manifest, adapter_file=adapter_file,
                      adapter_function=function)
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        result.update(state='failed', reason=str(error))
    return result


def mount_plugin(app, installation, host_services):
    with _MOUNT_LOCK:
        return _mount_plugin(app, installation, host_services)


def _mount_plugin(app, installation, host_services):
    if installation.get('state') != 'ready':
        return {'mounted': False, 'reason': installation.get('reason', 'Plugin indisponível.')}
    previous = getattr(app.state, 'neuro_plugin_mount', None)
    if previous is not None:
        if previous['version'] != installation['active_version']:
            raise RuntimeError('Reabra o Local Suite para ativar a nova versão do plugin.')
        return previous
    if host_services is None:
        raise RuntimeError('Serviços compartilhados do host não foram fornecidos.')
    code = Path(installation['code_dir']).resolve()
    path = _inside(code, installation['adapter_file'])
    if str(code) not in sys.path:
        sys.path.insert(0, str(code))
    spec = importlib.util.spec_from_file_location('_radai_neuro_adapter', path)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    service = getattr(adapter, installation['adapter_function'])(app, code, host_services=host_services)
    receipt = {'mounted': True, 'version': installation['active_version'], 'service': service}
    app.state.neuro_plugin_mount = receipt
    return receipt

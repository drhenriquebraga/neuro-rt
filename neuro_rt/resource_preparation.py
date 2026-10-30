"""Pinned optional resources using the Suite interpreter and its unchanged libraries.

Only a verified installer calls this module. It never invokes pip or an arbitrary
command, creates an interpreter, executes downloaded reference source, or writes
into the Suite's Python. Wheels contribute only missing packages in a private
directory appended after the base import paths by the scientific worker.
"""
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid
import zipfile

from .plugin_manifest import HostRuntimeUnavailable, validate_host_runtime
from .install_state import InstallFailure, _plain, _path, _identifier, _sha, _safe_remove_tree, _validate_name

RECIPE_SCHEMA = 'neuro-rt/resource-recipe/1'
RESOLVED_SCHEMA = 'neuro-rt/resolved-resources/1'
MAX_RESOURCE_FILE = 16 * 1024 ** 3
MAX_RESOURCE_TOTAL = 64 * 1024 ** 3


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode('utf-8')


def canonical_digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _digest(path):
    value = hashlib.sha256()
    with _plain(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def _normal_name(value):
    return re.sub(r'[-_.]+', '-', value).lower()


def _base_versions():
    base = Path(sys.executable).resolve().parent
    return {_normal_name(d.metadata['Name']): d.version
            for d in importlib.metadata.distributions()
            if Path(d.locate_file('')).resolve().is_relative_to(base)}


def _version(value):
    value = value.split('+', 1)[0]
    if not re.fullmatch(r'\d+(?:\.\d+)*', value):
        raise ValueError('Versão de dependência fora do contrato revisado.')
    return tuple(int(item) for item in value.split('.'))


def _matches(version, requirement):
    current = _version(version)
    for clause in requirement.split(','):
        match = re.fullmatch(r'\s*(==|!=|>=|<=|>|<)\s*(\d+(?:\.\d+)*)\s*', clause)
        if match is None:
            raise ValueError('Restrição de dependência fora do contrato revisado.')
        operation, required = match.groups()
        expected = _version(required)
        width = max(len(current), len(expected))
        left, right = current + (0,) * (width - len(current)), expected + (0,) * (width - len(expected))
        valid = {'==': left == right, '!=': left != right, '>=': left >= right,
                 '<=': left <= right, '>': left > right, '<': left < right}[operation]
        if not valid:
            return False
    return True


def _file_spec(entry):
    if not isinstance(entry, dict):
        raise ValueError('Artefato de recurso inválido.')
    _sha(entry.get('sha256'))
    if type(entry.get('size')) is not int or not 0 <= entry['size'] <= MAX_RESOURCE_FILE:
        raise ValueError('Tamanho de recurso inválido.')


def _download_spec(entry):
    _file_spec(entry)
    if not entry['size']:
        raise ValueError('Download de recurso vazio não é permitido.')
    name = entry.get('filename')
    _validate_name(name)
    if '/' in name:
        raise ValueError('Nome do download deve ser simples e relativo.')
    url = urllib.parse.urlparse(entry.get('url', ''))
    if url.scheme != 'https' or not url.netloc or url.username or url.password:
        raise ValueError('Fonte HTTPS original e sem credenciais é obrigatória.')


def _validate_recipe(recipe):
    if not isinstance(recipe, dict) or recipe.get('schema') != RECIPE_SCHEMA:
        raise ValueError('Receita de recursos inválida.')
    if any(key in recipe for key in ('host_python', 'python_executable', 'worker_python', 'runtimes')):
        raise ValueError('A receita não pode fornecer Python, runtimes ou comandos.')
    if recipe.get('python_abi', 'cp' + str(sys.version_info.major) + str(sys.version_info.minor)) != (
            'cp' + str(sys.version_info.major) + str(sys.version_info.minor)):
        raise HostRuntimeUnavailable('A ABI do Python da suíte não corresponde aos complementos fixados.')
    if 'platform' in recipe and (recipe['platform'] != 'win_amd64' or sys.platform != 'win32' or sys.maxsize <= 2 ** 32):
        raise HostRuntimeUnavailable('Os complementos desta receita exigem o Python Windows x64 da suíte.')
    if (not isinstance(recipe.get('protected_base'), dict) or not isinstance(recipe.get('wheels'), list)
            or not isinstance(recipe.get('downloads'), dict) or not isinstance(recipe.get('models'), list)
            or not isinstance(recipe.get('adapters'), dict)):
        raise ValueError('Receita de recursos incompleta.')
    seen = set()
    for wheel in recipe['wheels']:
        _download_spec(wheel)
        name = _normal_name(_identifier(wheel.get('name')))
        if name in seen or not isinstance(wheel.get('version'), str):
            raise ValueError('Complemento duplicado ou sem versão fixada.')
        seen.add(name)
        if not wheel['filename'].lower().endswith('.whl'):
            raise ValueError('Complementos devem ser wheels binários fixados.')
        if name in {'torch', 'numpy', 'scipy', 'simpleitk', 'monai', 'dipy'} or name.startswith('nvidia-'):
            raise ValueError('A receita não pode substituir bibliotecas protegidas da base.')
        if not isinstance(wheel.get('files'), dict) or not wheel['files']:
            raise ValueError('Wheel sem inventário de arquivos autenticado pela receita.')
        for filename, entry in wheel['files'].items():
            _validate_name(filename)
            if (Path(filename).suffix.lower() in ('.pth', '._pth', '.pyc', '.pyo', '.exe', '.bat', '.cmd', '.ps1', '.sh')
                    or '__pycache__' in Path(filename).parts):
                raise ValueError('Complementos não podem instalar Python, comandos ou hooks de inicialização.')
            _validate_name(entry.get('member'))
            _file_spec(entry)
        if any(name not in wheel['files'] for name in wheel.get('license_paths', [])):
            raise ValueError('Licença fora do inventário fixado do complemento.')
    for entry in recipe['downloads'].values():
        _download_spec(entry)
    for name, entry in recipe.get('extra_files', {}).items():
        _validate_name(name)
        _file_spec(entry)
        if entry.get('download') not in recipe['downloads']:
            raise ValueError('Texto de licença auxiliar sem fonte fixada.')
    models = set()
    for model in recipe['models']:
        key = (_identifier(model.get('id')), _identifier(model.get('revision')))
        if key in models or not isinstance(model.get('files'), dict) or not model['files']:
            raise ValueError('Modelo inválido ou duplicado na receita.')
        models.add(key)
        if not isinstance(model.get('license_paths'), list) or not model['license_paths']:
            raise ValueError('Modelo sem textos de licença fixados.')
        for name, entry in model['files'].items():
            _validate_name(name)
            _file_spec(entry)
            if entry.get('download') not in recipe['downloads']:
                raise ValueError('Arquivo do modelo sem download fixado.')
            if 'member' in entry:
                _validate_name(entry['member'])
        if any(name not in model['files'] for name in model['license_paths']):
            raise ValueError('Licença fora do inventário do modelo.')


def _verified_file(path, entry):
    path = _plain(path)
    if not path.is_file() or path.stat().st_size != entry['size'] or _digest(path) != entry['sha256']:
        raise ValueError('SHA256 ou tamanho do recurso não corresponde à identidade fixada.')
    return path


def _event(progress, stage, label, **details):
    if progress:
        progress(dict(stage=stage, label=label, **details))


def resource_cache_path(plugin_root, entry):
    """Content-addressed private download path, also consumed by local exporters."""
    _download_spec(entry)
    cache = _path(_plain(plugin_root).resolve(), 'cache/resources/downloads')
    return _path(cache, entry['sha256'] + '/' + entry['filename'])


def _cache_copy(source, target, entry):
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = _path(target.parent, target.name + '.partial-' + uuid.uuid4().hex)
    try:
        shutil.copyfile(source, partial)
        _verified_file(partial, entry)
        _plain(target)
        os.replace(partial, target)
        return target
    finally:
        partial.unlink(missing_ok=True)


def _fetch(entry, cache, source, progress):
    target = _path(cache, entry['sha256'] + '/' + entry['filename'])
    if target.exists():
        try:
            return _verified_file(target, entry)
        except (OSError, ValueError):
            pass  # Cache is mutable; replace corruption only after validating a fresh copy.
    legacy = _path(cache, entry['filename'])
    if legacy.is_file():
        try:
            _verified_file(legacy, entry)
        except (OSError, ValueError):
            pass  # A different legitimate revision may share this original filename.
        else:
            return _cache_copy(legacy, target, entry)
    if source is not None:
        mismatch = False
        prefixes = ('downloads/' + entry['sha256'] + '/', 'downloads/',
                    'runtime/resource_downloads/' + entry['sha256'] + '/', 'runtime/resource_downloads/',
                    'runtime/downloads/', 'models/_audit/', '')
        for relative in prefixes:
            candidate = _path(source, relative + entry['filename'])
            if candidate.is_file():
                try:
                    _verified_file(candidate, entry)
                except (OSError, ValueError):
                    mismatch = True
                    continue
                return _cache_copy(candidate, target, entry)
        if mismatch:
            raise ValueError('Nenhum arquivo local tem o SHA256 e tamanho do recurso fixado.')
        raise InstallFailure('LOCAL_RESOURCES_MISSING',
            'A fonte local não contém todos os recursos fixados. Use o pacote offline completo do START HERE.')
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = _path(target.parent, entry['filename'] + '.partial-' + uuid.uuid4().hex)
    copied = 0
    try:
        request = urllib.request.Request(entry['url'], headers={'User-Agent': 'NeuroRT-pinned-resources/1'})
        with urllib.request.urlopen(request, timeout=180) as incoming, partial.open('xb') as outgoing:
            for block in iter(lambda: incoming.read(1024 * 1024), b''):
                copied += len(block)
                if copied > entry['size']:
                    raise ValueError('Download excedeu o tamanho fixado.')
                outgoing.write(block)
                _event(progress, 'downloading', entry['filename'], downloaded_bytes=copied, total_bytes=entry['size'])
        _verified_file(partial, entry)
        os.replace(partial, target)
        return target
    finally:
        partial.unlink(missing_ok=True)


def _zip_members(archive):
    entries, seen, total = {}, set(), 0
    for entry in archive.infolist():
        name = entry.filename.rstrip('/') if entry.is_dir() else entry.filename
        _validate_name(name)
        if name.casefold() in seen:
            raise ValueError('Arquivo ZIP com caminhos duplicados.')
        seen.add(name.casefold())
        mode = entry.external_attr >> 16
        if (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR) or entry.flag_bits & 1
                or entry.external_attr & 0x400):
            raise ValueError('Links, reparse points e criptografia não são permitidos nos recursos.')
        total += entry.file_size
        if (entry.file_size > MAX_RESOURCE_FILE or total > MAX_RESOURCE_TOTAL
                or entry.file_size > max(entry.compress_size, 1) * 1000):
            raise ValueError('Recurso ZIP excede os limites de extração.')
        if not entry.is_dir():
            entries[entry.filename] = entry
    return entries


def _extract_wheel(archive_path, target, wheel):
    with zipfile.ZipFile(archive_path) as archive:
        entries = _zip_members(archive)
        for license_path in wheel.get('license_paths', []):
            if license_path not in entries:
                raise ValueError('Wheel sem licença original fixada.')
        for name, record in wheel['files'].items():
            entry = entries.get(record['member'])
            if entry is None or entry.file_size != record['size']:
                raise ValueError('Wheel diverge do inventário autenticado pela receita.')
            parts = name.split('/')
            first = parts[0]
            if not first.endswith('.dist-info'):
                module = first.split('.', 1)[0]
                if importlib.util.find_spec(module) is not None:
                    raise ValueError('Complemento tenta sombrear um módulo existente da base.')
            destination = _path(target, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise ValueError('Dois complementos reivindicam o mesmo arquivo.')
            with archive.open(entry) as incoming, destination.open('xb') as outgoing:
                shutil.copyfileobj(incoming, outgoing)
            _verified_file(destination, record)


def _inventory(folder):
    result = {}
    for path in sorted(folder.rglob('*')):
        _plain(path)
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = {'size': path.stat().st_size, 'sha256': _digest(path)}
    return result


def _verify_inventory(folder, inventory):
    actual = set()
    for path in folder.rglob('*'):
        _plain(path)
        if path.is_file():
            actual.add(path.relative_to(folder).as_posix())
    if actual != set(inventory):
        raise ValueError('Complemento contém arquivos ausentes ou fora do inventário fixado.')
    for name, entry in inventory.items():
        _verified_file(_path(folder, name), entry)


def _verify_model(folder, model):
    for name, entry in model['files'].items():
        _verified_file(_path(folder, name), entry)


def _prepare_model(model, recipe, root, stage, cache, source, progress):
    relative = 'models/' + model['id'] + '/' + model['revision']
    target = _path(root, relative)
    if target.exists():
        _verify_model(target, model)
        return relative
    local = None
    if source is not None:
        for candidate in (_path(source, relative), _path(source, 'models/' + model['id'])):
            if candidate.is_dir():
                _verify_model(candidate, model)
                local = candidate
                break
    pending = _path(stage, relative)
    pending.mkdir(parents=True)
    for name, entry in model['files'].items():
        destination = _path(pending, name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if local is not None:
            shutil.copyfile(_path(local, name), destination)
        else:
            downloaded = _fetch(recipe['downloads'][entry['download']], cache, source, progress)
            if 'member' in entry:
                with zipfile.ZipFile(downloaded) as archive:
                    entries = _zip_members(archive)
                    member = entries.get(entry['member'])
                    if member is None:
                        raise ValueError('Membro fixado ausente no arquivo do modelo.')
                    with archive.open(member) as incoming, destination.open('xb') as outgoing:
                        shutil.copyfileobj(incoming, outgoing)
            else:
                shutil.copyfile(downloaded, destination)
        _verified_file(destination, entry)
        _event(progress, 'validating', model['id'], file=name)
    (pending / 'provenance.json').write_bytes(canonical_bytes(model.get('provenance', {})))
    _verify_model(pending, model)
    target.parent.mkdir(parents=True, exist_ok=True)
    _plain(target)
    os.replace(pending, target)
    return relative


def probe_imports(adapters, *, extras, host_python, plugin_root):
    """Import required APIs in a child using the same exe, base before extras."""
    if not adapters:
        return {}
    for spec in adapters.values():
        if not isinstance(spec, dict) or not isinstance(spec.get('modules'), list) or any(
                not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', name)
                for name in spec['modules']):
            raise ValueError('Sonda de dependências fora do contrato fixado.')
    code = '''import importlib,json,pathlib,socket,sys
sys.path.append(sys.argv[1])
adapters=json.loads(sys.argv[2])
def no_network(*args,**kwargs): raise RuntimeError("Resource probes are offline")
socket.socket.connect=no_network
result={}
for name,spec in adapters.items():
    try:
        for module in spec["modules"]: importlib.import_module(module)
        result[name]={"available":True,"reason":""}
    except Exception as error:
        result[name]={"available":False,"reason":"Dependencias nao importaram ("+type(error).__name__+")."}
print("NEURO_RESOURCE_PROBE="+json.dumps(result),flush=True)
'''
    environment = dict(os.environ)
    environment.update(OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2',
                       ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS='2', PYTHONDONTWRITEBYTECODE='1',
                       MPLCONFIGDIR=str(_path(plugin_root, 'cache/mplconfig')))
    completed = subprocess.run([str(host_python), '-I', '-B', '-c', code, str(extras),
                                json.dumps(adapters)], capture_output=True, text=True, encoding='utf-8', errors='replace',
                               timeout=180, env=environment,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    lines = [line[len('NEURO_RESOURCE_PROBE='):] for line in completed.stdout.splitlines()
             if line.startswith('NEURO_RESOURCE_PROBE=')]
    if completed.returncode or len(lines) != 1:
        raise HostRuntimeUnavailable('Não foi possível confirmar a importação das dependências no Python da suíte.')
    capabilities = json.loads(lines[0])
    if any(not value['available'] for value in capabilities.values()):
        raise HostRuntimeUnavailable('Dependências dos motores não importaram no Python da suíte.')
    return capabilities


def _extra_plan(recipe):
    base = _base_versions()
    for name, requirement in recipe['protected_base'].items():
        if _normal_name(name) not in base or not _matches(base[_normal_name(name)], requirement):
            raise HostRuntimeUnavailable('A base do Local Suite é incompatível com os recursos solicitados; nenhuma biblioteca foi alterada.')
    missing, reused = [], {}
    for wheel in recipe['wheels']:
        name = _normal_name(wheel['name'])
        if name in base:
            if base[name] != wheel['version']:
                raise HostRuntimeUnavailable('Complemento conflita com uma biblioteca já instalada na base.')
            reused[name] = base[name]
        else:
            missing.append(wheel)
    extras_digest = canonical_digest({'wheels': missing, 'base': reused, 'extra_files': recipe.get('extra_files', {})})
    extra_inventory = {}
    for wheel in missing:
        for name, entry in wheel['files'].items():
            if name in extra_inventory:
                raise ValueError('Complementos reivindicam o mesmo arquivo.')
            extra_inventory[name] = {'size': entry['size'], 'sha256': entry['sha256']}
    for name, entry in recipe.get('extra_files', {}).items():
        if name in extra_inventory:
            raise ValueError('Licença auxiliar repete um arquivo do complemento.')
        extra_inventory[name] = {'size': entry['size'], 'sha256': entry['sha256']}
    return base, missing, reused, extras_digest, extra_inventory


def verify_extra_resources(recipe, descriptor, extras):
    """Recheck curated files against the trusted CODE recipe before any import."""
    _validate_recipe(recipe)
    _base, _missing, _reused, digest, inventory = _extra_plan(recipe)
    if descriptor.get('recipe_digest') != canonical_digest(recipe) or descriptor.get('extras_digest') != digest:
        raise ValueError('A identidade dos complementos não corresponde à base e receita ativas.')
    _verify_inventory(_plain(extras), inventory)


def prepare_offline_archives(recipe, *, plugin_root, progress=None):
    """Cache every original wheel for a portable local export, never install it.

    Even a wheel already provided by this source machine's base is retained:
    another compatible Suite may need that missing extra. Models are exported
    from their verified individual files, so their original ZIPs are unnecessary.
    No installation or first-use consent receipt is created by this helper.
    """
    _validate_recipe(recipe)
    root = _plain(plugin_root).resolve()
    cache = _path(root, 'cache/resources/downloads')
    entries = list(recipe['wheels'])
    for entry in recipe.get('extra_files', {}).values():
        download = recipe['downloads'][entry['download']]
        if not any(row['filename'] == download['filename'] for row in entries):
            entries.append(download)
    for entry in entries:
        _event(progress, 'preparing', entry['filename'])
        _fetch(entry, cache, None, progress)
    return entries


def prepare_resources(recipe, *, plugin_root, host_python, source_folder=None, progress=None):
    """Prepare only pinned missing extras and original model assets.

    An explicit source_folder is strictly offline. No base dependency is changed,
    and an already published model or extras component is never overwritten.
    The returned eight-field descriptor is bound to a canonical durable receipt.
    """
    validate_host_runtime(host_python)
    _validate_recipe(recipe)
    base, missing, reused, extras_digest, extra_inventory = _extra_plan(recipe)
    root = _plain(plugin_root).resolve()
    source = _plain(source_folder).resolve() if source_folder is not None else None
    digest = canonical_digest(recipe)
    extras_relative = 'extras/' + extras_digest + '/site-packages'
    extras = _path(root, extras_relative)
    receipt_relative = 'resources/' + digest + '.json'
    receipt_path = _path(root, receipt_relative)
    root.mkdir(parents=True, exist_ok=True)
    stage = _path(root, 'staging/resources-' + uuid.uuid4().hex)
    stage.mkdir(parents=True)
    cache = _path(root, 'cache/resources/downloads')
    try:
        if extras.exists():
            _verify_inventory(extras, extra_inventory)
        else:
            pending = _path(stage, 'site-packages')
            pending.mkdir()
            for wheel in missing:
                _event(progress, 'preparing', wheel['name'])
                archive = _fetch(wheel, cache, source, progress)
                _extract_wheel(archive, pending, wheel)
            for name, entry in recipe.get('extra_files', {}).items():
                original = _fetch(recipe['downloads'][entry['download']], cache, source, progress)
                destination = _path(pending, name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, destination)
            _verify_inventory(pending, extra_inventory)
            extras.parent.mkdir(parents=True, exist_ok=True)
            _plain(extras)
            os.replace(pending, extras)
        paths = {}
        for model in recipe['models']:
            _event(progress, 'preparing', model['id'])
            paths[model['id']] = _prepare_model(model, recipe, root, stage, cache, source, progress)
        _event(progress, 'validating', 'Conferindo dependências no Python da suíte.')
        capabilities = probe_imports(recipe['adapters'], extras=extras,
                                     host_python=host_python, plugin_root=root)
        receipt = {'schema': RESOLVED_SCHEMA, 'recipe_digest': digest, 'extras_digest': extras_digest,
                   'extras_relative_path': extras_relative, 'model_relative_paths': paths,
                   'capabilities': capabilities, 'extra_file_inventory': extra_inventory,
                   'base_versions': base, 'reused_base': reused, 'wheels': missing}
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = receipt_path.with_name(receipt_path.name + '.' + uuid.uuid4().hex + '.tmp')
        temporary.write_bytes(canonical_bytes(receipt))
        os.replace(temporary, receipt_path)
        descriptor = {key: receipt[key] for key in ('schema', 'recipe_digest', 'extras_digest',
                      'extras_relative_path', 'model_relative_paths', 'capabilities')}
        descriptor.update(receipt_relative_path=receipt_relative, receipt_sha256=_digest(receipt_path))
        _event(progress, 'complete', 'Recursos verificados.')
        return descriptor
    finally:
        if stage.exists():
            try:
                _safe_remove_tree(stage, root / 'staging')
            except OSError:
                pass  # Valid immutable components remain reusable after interrupted cleanup.

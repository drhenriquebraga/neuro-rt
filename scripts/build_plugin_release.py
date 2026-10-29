"""Deterministic allowlisted plugin packages; weights and runtimes stay out of Git.

Locks and component directories are explicit inputs. This builder never resolves
latest, invokes pip, downloads assets or copies a development virtualenv.
"""
import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
import os
import stat
from pathlib import Path
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from neuro_rt import install_state
from neuro_rt.model_registry import load_catalog

CODE_FILES = ('module.json', 'LICENSE', 'NOTICE', 'models.lock.json', 'requirements.txt')
CODE_DIRS = {'neuro_rt': {'.py'}, 'integration': {'.py'}, 'app': {'.py'},
             'web': {'.html', '.js', '.css', '.svg', '.json'},
             'licenses': {'.txt', '.md', '.html'}, 'catalog': {'.json'}}
PRIVATE_PARTS = {'.git', '.venv', '.aws', '.codex', '.agents', '__pycache__',
                 'data', 'config', 'jobs', 'cache', 'logs', 'tests'}
LICENSE_SUFFIXES = {'.txt', '.md', '.html', '.htm', '.rst'}


def _medical_image(name):
    name = name.lower()
    if name.endswith(('.dcm', '.dcm.gz', '.dicom', '.dicom.gz', '.ima', '.ima.gz')) or Path(name).name == 'dicomdir':
        return 'dicom'
    if name.endswith(('.nii', '.nii.gz')):
        return 'nifti'
    return None


def _license_name(name):
    file = Path(name)
    return file.suffix.lower() in LICENSE_SUFFIXES or file.name.upper() in ('LICENSE', 'COPYING', 'NOTICE')


def _license_text(name, raw):
    if not _license_name(name):
        return False
    if len(raw) > 2 * 1024 * 1024:
        return False
    try:
        value = raw.decode('utf-8-sig')
    except UnicodeError:
        return False
    return bool(value.strip()) and not any(ord(c) < 32 and c not in '\t\r\n' for c in value)


def validate_image_inventory(manifest, atlas):
    """Final boundary, independent of which collector added each record."""
    allowed = {item['path']: item for item in atlas.get('allowlist', [])}
    for record in manifest['files']:
        kind = _medical_image(record['path'])
        if kind == 'dicom':
            raise ValueError('DICOM não é permitido no inventário da release.')
        if kind != 'nifti':
            continue
        parts = record['path'].split('/')
        public = allowed.get('/'.join([parts[1], *parts[3:]])) if len(parts) >= 4 and parts[0] == 'models' else None
        if (len(parts) < 4 or parts[0] != 'models' or parts[1] != atlas.get('model_id')
                or not public or public.get('format') != 'nifti'
                or public.get('sha256') != record['sha256'] or public.get('size') != record['size']):
            raise ValueError('Imagem fora da identidade pública exata do atlas autorizado.')


def _archive_atlas(archive):
    name = 'code/catalog/atlas_assets.json'
    if name not in archive.namelist():
        return {}
    if archive.getinfo(name).file_size > 1024 * 1024:
        raise ValueError('Allowlist do atlas excede o limite permitido.')
    return json.loads(archive.read(name))


@dataclass(frozen=True)
class ReleaseArtifacts:
    offline: Path
    plugin: Path
    manifest: Path
    checksums: Path
    setup: Path | None = None
    setup_latest: Path | None = None


def _json(data):
    return (json.dumps(data, ensure_ascii=True, separators=(',', ':'), sort_keys=True) + '\n').encode()


def _record(name, path, checked_dirs=None):
    install_state._validate_name(name)
    checked_dirs = checked_dirs if checked_dirs is not None else set()
    # The immutable source tree is walked once. Rechecking every shared parent for
    # every library file makes an offline runtime inventory unnecessarily costly.
    # Each file is still lstat'ed; every distinct parent is checked for reparse/link.
    path = Path(path).absolute()
    for current in (path, *path.parents):
        if current in checked_dirs:
            break
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Links/reparse points não pertencem ao payload autorizado.')
        if stat.S_ISDIR(info.st_mode):
            checked_dirs.add(current)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return {'path': name, 'size': path.stat().st_size, 'sha256': digest.hexdigest()}


def source_code_files(root):
    root = Path(root)
    result = {}
    for name in CODE_FILES:
        path = root / name
        if path.is_file():
            result['code/' + name] = path
    for folder, extensions in CODE_DIRS.items():
        for path in (root / folder).rglob('*'):
            if (path.is_file() and path.suffix.lower() in extensions and
                    not PRIVATE_PARTS.intersection(path.relative_to(root).parts) and
                    not path.name.endswith(('.local.json', '.pyc'))):
                result['code/' + path.relative_to(root).as_posix()] = path
    return result


def _archive(path, manifest, payload, *, code_only=False):
    # Fixed timestamps/order/permissions: byte-identical for identical declared inputs.
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        entry = zipfile.ZipInfo('release-manifest.json', (2020, 1, 1, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(entry, _json(manifest))
        for name, source in sorted(payload.items()):
            if code_only and not name.startswith('code/'):
                continue
            entry = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry._compresslevel = 1
            entry.external_attr = 0o100644 << 16
            with archive.open(entry, 'w', force_zip64=True) as output:
                if isinstance(source, bytes):
                    output.write(source)
                else:
                    with source.open('rb') as stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b''):
                            output.write(block)


def build_release(version, catalog, locks, output_dir, *, root=ROOT, models_dir=None):
    """locks maps runtime ID to path, lock, python and license_paths, all pinned.

    The PLUGIN ZIP omits reusable components but includes their entire inventory.
    It is an upgrade artifact, never advertised as a standalone offline install.
    """
    root = Path(root)
    checked_dirs = set()
    models_dir = Path(models_dir or root / 'models')
    install_state._numeric_version(version)
    payload = {name: path.read_bytes() for name, path in source_code_files(root).items()}
    asset_manifest = root / 'scripts/model_assets_v1_manifest.json'
    if asset_manifest.is_file():
        payload['code/catalog/model_assets_v1_manifest.json'] = asset_manifest.read_bytes()
    load_catalog(catalog)
    raw_catalog = json.loads(Path(catalog).read_text(encoding='utf-8'))
    # Candidates have no distribution claim; no QTIM/Buti runtime is pulled in.
    raw_catalog['models'] = [m for m in raw_catalog['models'] if m.get('catalog_state') != 'candidate']
    models = raw_catalog['models']
    # Brain is an auxiliary dependency of the legacy Raidionics pipelines. Its
    # pinned inventory is kept in models.lock.json, not exposed as a selectable study.
    legacy_file = root / 'models.lock.json'
    legacy = json.loads(legacy_file.read_text(encoding='utf-8')).get('models', {}) if legacy_file.is_file() else {}
    inputs = [m for m in models if m.get('host_managed') is not True]
    if 'MRI_Brain' in legacy:
        brain = legacy['MRI_Brain']
        inputs.append({'id': 'MRI_Brain', 'revision': brain['release'], 'source_url': brain['source_url'],
            'artifacts': [{'path': n, 'sha256': h} for n, h in brain['files'].items()]})
    module = json.loads((root / 'module.json').read_text(encoding='utf-8'))
    if module['version'] != version:
        raise ValueError('Versão solicitada diverge de module.json.')
    used_runtime_ids = {m['runtime_id'] for m in models if m.get('host_managed') is not True}
    # Fixtures may intentionally have no models; the primary runtime remains explicit.
    used_runtime_ids |= set(module['runtimes'])
    if used_runtime_ids != set(locks):
        raise ValueError('Locks e runtimes declarados devem corresponder exatamente.')
    module['runtimes'] = {key: {'python': spec.get('python', 'python.exe')} for key, spec in locks.items()}
    payload['code/module.json'] = _json(module)
    payload['code/' + module['catalog']] = _json(raw_catalog)
    runtime_records = []
    for key, spec in locks.items():
        install_state._identifier(key)
        directory = Path(spec['path'])
        if (directory / 'pyvenv.cfg').exists() or (directory / 'Scripts/python.exe').exists():
            raise ValueError('Runtime deve ser portable embeddable, nunca virtualenv de desenvolvimento.')
        lock_digest = install_state._file_digest(spec['lock'])
        license_paths = list(spec['license_paths'])
        record = {'id': key, 'lock_digest': lock_digest,
                  'python': spec.get('python', 'python.exe'), 'license_paths': license_paths}
        runtime_records.append(record)
        for required in [record['python'], *license_paths]:
            if not install_state._path(directory, required).is_file():
                raise ValueError('Runtime incompleto ou licença ausente.')
        for path in directory.rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix in ('.pyc', '.pyo'):
                continue
            if _medical_image(path.name):
                continue
            name = f'runtimes/{key}/{lock_digest}/' + path.relative_to(directory).as_posix()
            payload[name] = path
    atlas_file = root / 'catalog/atlas_assets.json'
    atlas = json.loads(atlas_file.read_text(encoding='utf-8')) if atlas_file.is_file() else {}
    allowed_atlas = {a['path']: a for a in atlas.get('allowlist', [])}
    model_records = []
    for model in inputs:
        key, revision = model['id'], model['revision']
        install_state._identifier(key)
        install_state._identifier(revision)
        directory = models_dir / key / revision
        if not directory.is_dir():
            directory = models_dir / key  # Explicit builder input may be the audited dev flat cache.
        licenses = []
        selected = set()
        for artifact in model['artifacts']:
            name = artifact['path']
            path = install_state._path(directory, name)
            actual = _record('models/' + key + '/' + revision + '/' + name, path, checked_dirs)
            if actual['sha256'] != artifact['sha256'] or artifact.get('size', actual['size']) != actual['size']:
                raise ValueError('Artefato do modelo diverge do catálogo fixado.')
            if name.lower().endswith(('.nii', '.nii.gz', '.dcm')):
                public = allowed_atlas.get(key + '/' + name)
                if (key != atlas.get('model_id') or not public or public['sha256'] != actual['sha256']
                        or public['size'] != actual['size'] or name.lower().endswith('.dcm')):
                    raise ValueError('Imagem não pertence à allowlist exata do atlas público.')
            selected.add(name)
            payload[actual['path']] = path
        # License identity is included in the same inventory. Original texts, not summaries.
        for path in directory.rglob('*'):
            if (path.is_file() and path.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE'))
                    and _license_name(path.name) and path.stat().st_size <= 2 * 1024 * 1024
                    and _license_text(path.name, path.read_bytes())):
                name = path.relative_to(directory).as_posix()
                licenses.append(name)
                selected.add(name)
                payload[f'models/{key}/{revision}/' + name] = path
        if not licenses:
            raise ValueError('Modelo sem texto de licença original.')
        if key in legacy:
            # Reconstruct provenance exclusively from the reviewed, committed lock.
            # Do not copy arbitrary local receipts or their filesystem details.
            payload[f'models/{key}/{revision}/provenance.json'] = _json(legacy[key])
        model_records.append({'id': key, 'revision': revision, 'license_paths': sorted(licenses),
                              'source_url': model.get('source_url'),
                              'source_revision': model.get('source_revision', revision)})
    code_licenses = [n[5:] for n in payload if n.startswith('code/licenses/') or n == 'code/LICENSE']
    if not code_licenses:
        raise ValueError('Código sem licença.')
    files = []
    for name, value in sorted(payload.items()):
        files.append({'path': name, 'size': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
                     if isinstance(value, bytes) else _record(name, value, checked_dirs))
    manifest = {'schema': install_state.SCHEMA, 'plugin_id': 'neuro-rt', 'version': version,
        'host_min_version': module['host_min_version'], 'python': module.get('python'),
        'runtime': {k: runtime_records[0][k] for k in ('id', 'lock_digest', 'python')},
        'runtimes': runtime_records, 'models': model_records,
        'code_license_paths': sorted(code_licenses), 'files': files}
    install_state._manifest_shape(manifest)
    validate_image_inventory(manifest, atlas)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    offline = out / f'NEURO_RT_OFFLINE_v{version}.zip'
    plugin = out / f'NEURO_RT_PLUGIN_v{version}.zip'
    _archive(offline, manifest, payload)
    return _finish_release(root, module, manifest, offline, payload, out)


def _finish_release(root, module, manifest, offline, payload, out, *, verified=False):
    version = manifest['version']
    plugin = out / f'NEURO_RT_PLUGIN_v{version}.zip'
    _archive(plugin, manifest, payload, code_only=True)
    manifest_path = out / 'release-manifest.json'
    manifest_path.write_bytes(_json(manifest))
    setup = setup_latest = None
    setup_scripts = ('INSTALL.ps1', 'UPDATE.ps1', 'PREPARE_LATEST.ps1')
    if all((root / 'installer' / n).is_file() for n in setup_scripts):
        setup_payload = {'installer/' + n: root / 'installer' / n for n in setup_scripts}
        for name in ('__init__', 'plugin_manifest', 'model_paths', 'model_registry', 'install_state', 'plugin_update'):
            setup_payload['neuro_rt/' + name + '.py'] = root / 'neuro_rt' / (name + '.py')
        for name in ('LICENSE', 'NOTICE'):
            setup_payload[name] = root / name
        setup_manifest = {'schema': 'neuro-rt/setup/1', 'version': version,
            'host_min_version': module['host_min_version'],
            'files': [_record(name, p) for name, p in sorted(setup_payload.items())],
            'offline_asset': offline.name, 'offline_sha256': install_state._file_digest(offline)}
        setup_payload['setup-manifest.json'] = _json(setup_manifest)
        setup = out / f'NEURO_RT_SETUP_v{version}.zip'
        setup_latest = out / 'NEURO_RT_SETUP_LATEST.zip'
        _archive(setup, manifest, setup_payload)
        import shutil
        shutil.copyfile(setup, setup_latest)
    checksums = out / 'SHA256SUMS.txt'
    checksums.write_text(''.join(install_state._file_digest(p) + '  ' + p.name + '\n'
        for p in (offline, plugin, manifest_path, setup, setup_latest) if p is not None), encoding='ascii')
    if not verified:
        verify_release(manifest_path, offline)
    return ReleaseArtifacts(offline, plugin, manifest_path, checksums, setup, setup_latest)


def refresh_code_release(offline, manifest, *, root=ROOT, output_dir=None):
    """Snapshot final code while reusing inventoried compressed component entries.

    The resulting ZIP is fully verified once, including every preserved SHA256.
    No source component is executed or extracted while copying. This avoids
    rereading development environments or recompressing immutable payloads.
    """
    offline, manifest, root = Path(offline), Path(manifest), Path(root)
    previous = json.loads(manifest.read_text(encoding='utf-8'))
    install_state._manifest_shape(previous)
    with zipfile.ZipFile(offline) as source:
        validate_image_inventory(previous, _archive_atlas(source))
    payload = {name: path.read_bytes() for name, path in source_code_files(root).items()}
    canonical = root / 'scripts/model_assets_v1_manifest.json'
    if canonical.is_file():
        payload['code/catalog/model_assets_v1_manifest.json'] = canonical.read_bytes()
    module = json.loads(payload['code/module.json'])
    payload['code/module.json'] = _json(module)
    catalog_path = root / module['catalog']
    load_catalog(catalog_path)
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    catalog['models'] = [m for m in catalog['models'] if m['catalog_state'] != 'candidate']
    payload['code/' + module['catalog']] = _json(catalog)
    records = [r for r in previous['files'] if not r['path'].startswith('code/')]
    records += [{'path': name, 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                for name, raw in payload.items()]
    updated = dict(previous, version=module['version'], host_min_version=module['host_min_version'],
        python=module.get('python'), files=sorted(records, key=lambda r: r['path']),
        code_license_paths=sorted(n[5:] for n in payload if n.startswith('code/licenses/') or n == 'code/LICENSE'))
    install_state._manifest_shape(updated)
    atlas_name = 'code/catalog/atlas_assets.json'
    validate_image_inventory(updated, json.loads(payload[atlas_name]) if atlas_name in payload else {})
    out = Path(output_dir or offline.parent)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f'NEURO_RT_OFFLINE_v{module["version"]}.zip'
    temporary = out / (target.name + '.refresh')
    temporary_manifest = out / 'release-manifest.refresh.json'
    temporary_manifest.write_bytes(_json(updated))
    try:
        with zipfile.ZipFile(offline) as source, zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED,
                compresslevel=1, allowZip64=True) as archive:
            if source.getinfo('release-manifest.json').file_size > install_state.MAX_MANIFEST * 2:
                raise ValueError('Manifesto de origem excede o limite do construtor.')
            if json.loads(source.read('release-manifest.json')) != previous:
                raise ValueError('Manifesto externo não corresponde ao ZIP de origem.')
            originals = source.infolist()
            expected_names = {r['path'] for r in previous['files']} | {'release-manifest.json'}
            if len(originals) != len(expected_names) or {i.filename for i in originals} != expected_names:
                raise ValueError('ZIP de origem contém arquivos extras ou duplicados.')
            offsets = sorted(originals, key=lambda info: info.header_offset)
            ends = {info.filename: offsets[i+1].header_offset if i+1 < len(offsets) else source.start_dir
                    for i, info in enumerate(offsets)}
            # Preserve local headers and compressed streams. ZipFile writes fresh
            # central records with the adjusted offsets; final verification checks
            # names, flags, bounds, CRC, and every uncompressed SHA256 before publish.
            for info in offsets:
                if not info.filename.startswith(('models/', 'runtimes/')):
                    continue
                cloned = copy.copy(info)
                cloned.header_offset = archive.fp.tell()
                source.fp.seek(info.header_offset)
                remaining = ends[info.filename] - info.header_offset
                while remaining:
                    block = source.fp.read(min(1024 * 1024, remaining))
                    if not block:
                        raise ValueError('ZIP de origem truncado.')
                    archive.fp.write(block)
                    remaining -= len(block)
                archive.filelist.append(cloned)
                archive.NameToInfo[cloned.filename] = cloned
                archive.start_dir = archive.fp.tell()
                archive._didModify = True
            for record in updated['files']:
                name = record['path']
                if not name.startswith('code/'):
                    continue
                entry = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry._compresslevel = 1
                entry.external_attr = 0o100644 << 16
                with archive.open(entry, 'w', force_zip64=True) as output:
                    output.write(payload[name])
            entry = zipfile.ZipInfo('release-manifest.json', (2020, 1, 1, 0, 0, 0))
            archive.writestr(entry, _json(updated))
        verify_release(temporary_manifest, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
        temporary_manifest.unlink(missing_ok=True)
    return _finish_release(root, module, updated, target, payload, out, verified=True)


def verify_release(manifest, artifacts):
    expected = json.loads(Path(manifest).read_text(encoding='utf-8'))
    with zipfile.ZipFile(artifacts) as archive:
        actual, _, _, entries = install_state._inspect_zip(archive)
        if actual != expected:
            raise ValueError('Manifesto externo difere do pacote.')
        validate_image_inventory(actual, _archive_atlas(archive))
        for record in actual['files']:
            if record['path'] not in entries:
                raise ValueError('Offline incompleto.')
            digest = hashlib.sha256()
            with archive.open(record['path']) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            if digest.hexdigest() != record['sha256']:
                raise ValueError('SHA256 do payload divergente.')
        license_names = ['code/' + path for path in actual['code_license_paths']]
        for component, prefix in [('runtimes', 'runtimes'), ('models', 'models')]:
            for item in actual[component]:
                revision = item['lock_digest'] if component == 'runtimes' else item['revision']
                license_names += [f'{prefix}/{item["id"]}/{revision}/' + name for name in item['license_paths']]
        for name in license_names:
            if archive.getinfo(name).file_size > 2 * 1024 * 1024 or not _license_text(name, archive.read(name)):
                raise ValueError('Componente sem texto de licença permitido.')
        with tempfile.TemporaryDirectory(prefix='verify-code-', dir=Path(artifacts).parent) as tmp:
            code = Path(tmp)
            for name in entries:
                if name.startswith('code/'):
                    destination = install_state._path(code, name[5:])
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.read(name))
            install_state._verify_catalog(code, actual)
    return {'ok': True, 'version': actual['version'], 'files': len(actual['files'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--runtime-spec', type=Path)
    source.add_argument('--refresh-from', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--version', default='1.0.0')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    if args.refresh_from:
        result = refresh_code_release(args.refresh_from,
            args.manifest or args.refresh_from.parent / 'release-manifest.json', output_dir=args.output)
    else:
        specs = json.loads(args.runtime_spec.read_text(encoding='utf-8'))
        result = build_release(args.version, ROOT / 'catalog/models.json', specs, args.output)
    print(json.dumps({k: str(v) for k, v in result.__dict__.items()}))


if __name__ == '__main__':
    main()

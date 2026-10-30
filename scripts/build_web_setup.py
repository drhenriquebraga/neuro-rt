"""Build the two small, deterministic public setups using the existing host.

Only allowlisted UTF-8 code, notices and three installer entrypoints are shipped.
No dependency resolution, download, Python environment or model staging occurs.
"""
import argparse
import hashlib
import io
import os
from pathlib import Path
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from neuro_rt import install_state
from neuro_rt.model_registry import load_catalog
from neuro_rt.plugin_manifest import read_manifest
from scripts.build_plugin_release import CODE_DIRS, CODE_FILES, PRIVATE_PARTS, _archive, source_code_files

INSTALLERS = ('INSTALL.ps1', 'UPDATE.ps1', 'PREPARE_LATEST.ps1')
MAX_SETUP_SIZE = 3 * 1024 * 1024
_PRIVATE = {part.casefold() for part in PRIVATE_PARTS} | {
    'runtime', 'runtimes', 'models', 'python', 'site-packages', 'venv', 'host_updates'}
_ASSET_MANIFEST = 'code/catalog/model_assets_v1_manifest.json'


def _source_bytes(root, name, source, *, asset_fallback=False):
    """Enforce the final boundary even if a collector supplies an unsafe entry."""
    install_state._validate_name(name)
    parts = name.split('/')
    if len(parts) < 2 or parts[0] != 'code':
        raise ValueError('O setup permite somente código autorizado.')
    relative = '/'.join(parts[1:])
    if (any(part.casefold() in _PRIVATE for part in parts[1:]) or
            parts[-1].lower().endswith(('.local.json', '.pyc'))):
        raise ValueError('Diretório ou arquivo privado no payload do setup.')
    allowed = (relative in CODE_FILES or
               relative in {'installer/' + script for script in INSTALLERS} or
               (len(parts) >= 3 and parts[1] in CODE_DIRS and
                Path(parts[-1]).suffix.lower() in CODE_DIRS[parts[1]]))
    if not allowed:
        raise ValueError('Arquivo fora da allowlist de código do setup.')
    expected = root / relative
    if asset_fallback:
        expected = root / 'scripts/model_assets_v1_manifest.json'
    # Reject links before resolve/read; resolving alone would conceal junctions.
    source = install_state._plain(source).resolve()
    if not source.is_relative_to(root) or source != expected:
        raise ValueError('Origem do código deve corresponder ao caminho autorizado.')
    raw = source.read_bytes()
    if raw.startswith((b'MZ', b'PK\x03\x04', b'\x7fELF')):
        raise ValueError('Payload binário não é permitido no setup.')
    install_state._verify_host_source(io.BytesIO(raw))
    return raw


def build_web_setup(output_dir, *, root=ROOT) -> dict:
    """Return setup/latest paths, their common SHA256 and the CODE inventory."""
    root = install_state._plain(root).resolve()
    install_state._plain(root / 'module.json')
    module = read_manifest(root / 'module.json')
    if module.execution_mode != 'host':
        raise ValueError('O setup público exige execution_mode=host no repositório.')
    if (module.host_min_version is None or
            install_state._numeric_version(module.host_min_version) < (8, 11)):
        raise ValueError('O setup público exige Local Suite 8.11 ou posterior.')
    sources = source_code_files(root)
    for script in INSTALLERS:
        sources['code/installer/' + script] = root / 'installer' / script
    fallback = _ASSET_MANIFEST not in sources and (root / 'scripts/model_assets_v1_manifest.json').is_file()
    if fallback:
        sources[_ASSET_MANIFEST] = root / 'scripts/model_assets_v1_manifest.json'
    payload = {name: _source_bytes(root, name, source,
                   asset_fallback=fallback and name == _ASSET_MANIFEST)
               for name, source in sorted(sources.items())}
    required = {'code/module.json', 'code/LICENSE', 'code/NOTICE',
                'code/' + module.catalog, 'code/' + module.adapter.split(':')[0]}
    if not required.issubset(payload):
        raise ValueError('Código, catálogo, adaptador ou licença obrigatória ausente.')
    load_catalog(root / module.catalog)
    manifest = {
        'schema': install_state.SCHEMA, 'plugin_id': 'neuro-rt',
        'version': module.version, 'execution_mode': 'host', 'runtime': None,
        'runtimes': [], 'models': [],
        'code_license_paths': sorted(name[5:] for name in payload
                                     if name in ('code/LICENSE', 'code/NOTICE') or
                                     name.startswith('code/licenses/')),
        'files': [{'path': name, 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                  for name, raw in sorted(payload.items())],
    }
    install_state._manifest_shape(manifest)
    output = install_state._plain(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    setup = output / f'NEURO_RT_SETUP_v{module.version}.zip'
    latest = output / 'NEURO_RT_SETUP_LATEST.zip'
    # Publish only after the entire small ZIP passes the shared installation gate.
    with tempfile.TemporaryDirectory(prefix='.web-setup-', dir=output) as temporary:
        staged = Path(temporary) / setup.name
        _archive(staged, manifest, payload)
        if staged.stat().st_size > MAX_SETUP_SIZE:
            raise ValueError('O setup excede o limite de 3 MiB; revise a allowlist.')
        with zipfile.ZipFile(staged) as archive:
            install_state._inspect_zip(archive)
        raw = staged.read_bytes()
        alias = Path(temporary) / latest.name
        alias.write_bytes(raw)
        for target in (setup, latest):
            install_state._plain(target)
        os.replace(staged, setup)
        os.replace(alias, latest)
    return {'setup': setup, 'latest': latest, 'manifest': manifest,
            'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    result = build_web_setup(parser.parse_args().output)
    print(result['setup'])
    print(result['latest'])
    print('SHA256 ' + result['sha256'])


if __name__ == '__main__':
    main()

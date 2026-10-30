"""Download and verify the four selected public models; inference stays offline.

The adjacent manifest pins author revisions, original URLs, sizes and SHA256.
No remote code is imported and only archive members on the allowlist are copied.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path(__file__).with_name('model_assets_v1_manifest.json')
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_file(path, expected_sha256, expected_size, kind):
    path = Path(path)
    with path.open('rb') as stream:
        prefix = stream.read(1024).lstrip().lower()
    if kind != 'html' and prefix.startswith((b'<!doctype html', b'<html', b'<head')):
        raise ValueError(f'HTML recebido no lugar do artefato: {path.name}')
    if path.stat().st_size != expected_size:
        raise ValueError(f'Tamanho divergente: {path.name}')
    if sha256(path) != expected_sha256:
        raise ValueError(f'SHA256 divergente: {path.name}')
    if kind == 'zip':
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError(f'ZIP corrompido: {path.name}')
    elif kind == 'torch' and not prefix.startswith((b'pk\x03\x04', b'\x80')):
        raise ValueError(f'Formato PyTorch inválido: {path.name}')
    return path


def extract_allowed(archive_path, destination, members):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            target = (destination / info.filename).resolve()
            if (not target.is_relative_to(destination) or
                    (info.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('ZIP com caminho ou link inseguro.')
        for member, relative in members.items():
            target = (destination / relative).resolve()
            if not target.is_relative_to(destination):
                raise ValueError('Destino ZIP fora da pasta do modelo.')
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open('wb') as output:
                shutil.copyfileobj(source, output)


def fetch(entry, cache, offline=False):
    path = Path(cache) / entry['filename']
    if path.exists():
        return verify_file(path, entry['sha256'], entry['size'], entry['format'])
    if offline:
        raise FileNotFoundError(f'Cache incompleto: {path.name}')
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + '.partial')
    request = urllib.request.Request(entry['url'], headers={'User-Agent': 'NeuroRT-model-assets/1'})
    try:
        with urllib.request.urlopen(request, timeout=180) as response, partial.open('wb') as output:
            if entry['format'] != 'html' and 'text/html' in response.headers.get('Content-Type', '').lower():
                raise ValueError(f'HTML recebido: {path.name}')
            shutil.copyfileobj(response, output)
        verify_file(partial, entry['sha256'], entry['size'], entry['format'])
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return path


def verify_model(model_id, models_dir):
    spec = MANIFEST['models'][model_id]
    folder = Path(models_dir) / model_id
    for relative, entry in spec['files'].items():
        verify_file(folder / relative, entry['sha256'], entry['size'], entry['format'])
    return folder


def prepare(model_id, models_dir, cache, offline=False):
    spec = MANIFEST['models'][model_id]
    destination = Path(models_dir).resolve() / model_id
    if destination.exists():
        return verify_model(model_id, models_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    downloads = {}
    for entry in spec['files'].values():
        key = entry['download']
        if key not in downloads:
            downloads[key] = fetch(MANIFEST['downloads'][key], cache, offline)
    with tempfile.TemporaryDirectory(prefix='asset_stage_', dir=destination.parent) as tmp:
        stage = Path(tmp)
        for relative, entry in spec['files'].items():
            source = downloads[entry['download']]
            if 'member' in entry:
                extract_allowed(source, stage, {entry['member']: relative})
            else:
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            verify_file(stage / relative, entry['sha256'], entry['size'], entry['format'])
        receipt = {'schema': 'neuro-rt/model-assets/1', 'model_id': model_id,
                   'revision': spec['revision'], 'license': spec['license'],
                   'files': spec['files'], 'downloads': {
                       key: MANIFEST['downloads'][key] for key in downloads}}
        (stage / 'provenance.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        shutil.copytree(stage, destination)
    return verify_model(model_id, models_dir)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', nargs='+', choices=list(MANIFEST['models']), default=list(MANIFEST['models']))
    parser.add_argument('--models-dir', type=Path, default=ROOT / 'models')
    parser.add_argument('--cache', type=Path, default=ROOT / 'runtime' / 'model_assets_v1_downloads')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    for model_id in args.models:
        folder = (verify_model(model_id, args.models_dir) if args.verify_only else
                  prepare(model_id, args.models_dir, args.cache, args.offline))
        print(f'Íntegro: {model_id} ({folder})', flush=True)


if __name__ == '__main__':
    main()

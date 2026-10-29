"""Monta Python 3.10 embeddable + wheels CPU, sem instalação global ou admin."""
import hashlib
import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip'
PRIMARY_PYTHON_SHA256 = '608619f8619075629c9c69f361352a0da6ed7e62f83a0e19c63e0ea32eb7629d'
SCIENTIFIC_URL = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip'
SCIENTIFIC_SHA256 = '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3'


def _locked_packages(lock):
    result = {}
    for line in Path(lock).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('-r '):
            result.update(_locked_packages(Path(lock).parent / line[3:].strip()))
        elif '==' in line:
            key, version = line.split('==', 1)
            result[key.lower().replace('_', '-')] = version
        else:
            raise ValueError('Lock deve conter somente versões fixadas e inclusões locais.')
    return result


def build_scientific_portable(destination, *, archive=None, site_packages=None, lock=None):
    """Rehome audited packages onto CPython embed, never copy venv launchers/paths.

    All locked distributions must match the previously audited environment. The
    output has its own Python DLL/stdlib and a relative ._pth file. No global Python
    or development venv is consulted at runtime.
    """
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Runtime portátil existente é imutável; selecione outro destino.')
    archive = Path(archive or ROOT / 'runtime/downloads/python-3.12.10-embed-amd64.zip')
    site_packages = Path(site_packages or ROOT / 'runtime/model_assets_v1_env/Lib/site-packages')
    lock = Path(lock or ROOT / 'scripts/scientific_adapters_runtime.lock.txt')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SCIENTIFIC_SHA256:
        raise ValueError('CPython embeddable difere do SHA256 fixado.')
    expected = _locked_packages(lock)
    installed = {d.metadata['Name'].lower().replace('_', '-'): d.version
                 for d in importlib.metadata.distributions(path=[str(site_packages)])}
    if any(installed.get(name) != version for name, version in expected.items()):
        raise ValueError('Ambiente científico diverge do lock revisado.')
    destination.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zipped:
        for entry in zipped.infolist():
            if not (destination / entry.filename).resolve().is_relative_to(destination.resolve()):
                raise ValueError('Caminho inválido no CPython embeddable.')
        zipped.extractall(destination)
    shutil.copytree(site_packages, destination / 'Lib/site-packages',
        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo', 'pip', 'pip-*.dist-info'))
    (destination / 'python312._pth').write_text('python312.zip\n.\nLib/site-packages\nimport site\n', encoding='ascii')
    # Preserve original Python and package licenses; each dist-info remains in place.
    provenance = {'python_version': '3.12.10', 'source_url': SCIENTIFIC_URL,
        'archive_sha256': SCIENTIFIC_SHA256, 'locked_packages': expected,
        'lock_sha256': hashlib.sha256(lock.read_bytes()).hexdigest(),
        'layout': 'cpython-embed-relative-pth', 'requires_global_python': False}
    (destination / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    environment = dict(os.environ)
    environment['MPLCONFIGDIR'] = str(ROOT / 'runtime/mplconfig')
    subprocess.run([str(destination / 'python.exe'), '-I', '-B', '-c',
        'import torch,monai,dipy,ants,SimpleITK,pydicom,nibabel; '
        'print("Portable scientific runtime OK")'], check=True, cwd=destination, env=environment)
    return destination


def main():
    destination = ROOT / 'python'
    if destination.exists():
        raise RuntimeError('Runtime portátil já existe. Preserve-o; não será sobrescrito.')
    cache = ROOT / 'runtime' / 'downloads'
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / 'python-3.10.11-embed-amd64.zip'
    if not archive.is_file():
        print('Baixando Python 3.10.11 embeddable oficial...', flush=True)
        with urllib.request.urlopen(URL, timeout=60) as response, archive.open('wb') as handle:
            shutil.copyfileobj(response, handle)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != PRIMARY_PYTHON_SHA256:
        raise ValueError('CPython Raidionics difere do SHA256 fixado.')
    build = Path(tempfile.mkdtemp(prefix='python_build_', dir=ROOT / 'runtime')).resolve()
    with zipfile.ZipFile(archive) as zipped:
        for name in zipped.namelist():
            if not (build / name).resolve().is_relative_to(build):
                raise ValueError('Caminho inválido no arquivo Python.')
        zipped.extractall(build)
    (build / 'python310._pth').write_text('python310.zip\n.\nLib/site-packages\n..\nimport site\n')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                    '--target', str(build / 'Lib/site-packages'), '--only-binary=:all:',
                    '--platform', 'win_amd64', '--python-version', '3.10', '--implementation', 'cp',
                    '--abi', 'cp310', '-r', str(ROOT / 'scripts/raidionics_runtime.lock.txt')], check=True)
    subprocess.run([str(build / 'python.exe'), '-c',
                    'import raidionicsseg.fit,SimpleITK,nibabel,numpy,pydicom,onnxruntime; '
                    'print("Runtime portatil CPU importado com sucesso.")'], cwd=ROOT, check=True)
    receipt = {'python_version':'3.10.11', 'source_url':URL,
               'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
               'requirements':(ROOT / 'scripts/raidionics_runtime.lock.txt').read_text(),
               'lock_sha256':hashlib.sha256((ROOT / 'scripts/raidionics_runtime.lock.txt').read_bytes()).hexdigest()}
    (build / 'provenance.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    build.rename(destination)
    print('Runtime pronto em python/. Licenças de dependências preservadas nos dist-info.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--scientific', action='store_true')
    parser.add_argument('--destination', type=Path, default=ROOT / 'runtime/neuro-scientific-portable')
    args = parser.parse_args()
    if args.scientific:
        print(build_scientific_portable(args.destination))
    else:
        main()

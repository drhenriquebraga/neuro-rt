"""Monta Python 3.10 embeddable + wheels CPU, sem instalação global ou admin."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip'


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
                    '--abi', 'cp310', '-r', str(ROOT / 'requirements.txt')], check=True)
    subprocess.run([str(build / 'python.exe'), '-c',
                    'import raidionicsseg.fit,SimpleITK,nibabel,numpy,pydicom,onnxruntime; '
                    'print("Runtime portatil CPU importado com sucesso.")'], cwd=ROOT, check=True)
    receipt = {'python_version':'3.10.11', 'source_url':URL,
               'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
               'requirements':(ROOT / 'requirements.txt').read_text()}
    (build / 'provenance.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    build.rename(destination)
    print('Runtime pronto em python/. Licenças de dependências preservadas nos dist-info.', flush=True)


if __name__ == '__main__':
    main()

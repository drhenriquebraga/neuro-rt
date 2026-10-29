"""Entrega por allowlist; nunca inclui imagens, jobs ou configuração local."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from neuro_rt.catalog import MODELS, BRAIN, validate_model_folder
from neuro_rt import __version__

SOURCE_FILES = ['README.md','AGENTS.md','LICENSE','NOTICE','module.json','models.lock.json',
                'requirements.txt','requirements-dev.txt','neuro_rt.example.json',
                'INICIAR.cmd','PREPARAR.cmd']
SOURCE_DIRS = ['neuro_rt','web','integration','catalog','app','tools','licenses','scripts','docs','tests','installer','.github']
IMAGE_SUFFIXES = ('.dcm','.nii','.nii.gz')


def source_files(root):
    root = Path(root)
    files = [root / name for name in SOURCE_FILES]
    files += [file for name in SOURCE_DIRS for file in (root / name).rglob('*')
              if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc']
    if any(not file.is_file() for file in files):
        raise ValueError('Fonte ou licença obrigatória ausente.')
    return files


def package(offline=False, runtime_spec=None):
    if runtime_spec is not None:
        from scripts.build_plugin_release import build_release
        result = build_release(__version__, ROOT / 'catalog/models.json',
            json.loads(Path(runtime_spec).read_text(encoding='utf-8')), ROOT / 'dist')
        return result.offline if offline else result.plugin
    if offline:
        raise ValueError('Offline instalável exige --runtime-spec com os dois runtimes portáteis fixados.')
    files = source_files(ROOT)
    if offline:
        if not (ROOT / 'python/provenance.json').is_file():
            raise ValueError('Prepare e confira o runtime portátil antes de empacotar offline.')
        for model in [BRAIN, *MODELS]:
            validate_model_folder(ROOT / 'models' / model['id'], model)
        for name in ('python','models'):
            files += [file for file in (ROOT / name).rglob('*') if file.is_file()
                      and '__pycache__' not in file.parts and file.suffix != '.pyc'
                      and not file.name.lower().endswith(IMAGE_SUFFIXES)]
    if any(file.name.lower().endswith(IMAGE_SUFFIXES) for file in files):
        raise ValueError('Imagem clínica/sintética não pode entrar no pacote.')
    out = ROOT / 'dist'
    out.mkdir(exist_ok=True)
    name = f'NEURO_RT_SOURCE_v{__version__}.zip'
    path = out / name
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1 if offline else 6) as zipped:
        for file in sorted(set(files)):
            zipped.write(file, file.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(path) as zipped:
        if zipped.testzip() is not None:
            raise RuntimeError('Falha na integridade do pacote ZIP.')
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024),b''):
            digest.update(chunk)
    (out / (name + '.sha256')).write_text(digest.hexdigest() + '  ' + name + '\n')
    print(json.dumps({'file':str(path),'size_bytes':path.stat().st_size,'sha256':digest.hexdigest()}))
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--runtime-spec', type=Path)
    args = parser.parse_args()
    package(args.offline, args.runtime_spec)

"""Preparo explícito; único comando que baixa pesos. Inferência é offline."""
import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from neuro_rt.catalog import BASE_URL, BRAIN, MODELS, get_model, validate_model_folder


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def install_archive(archive, model, models_dir):
    archive, models_dir = Path(archive), Path(models_dir).resolve()
    if archive.stat().st_size != model['size']:
        raise ValueError('Tamanho do arquivo não corresponde à release fixada.')
    lock = json.loads((ROOT / 'models.lock.json').read_text(encoding='utf-8'))
    expected = lock['models'][model['id']]['archive_sha256']
    if sha256(archive) != expected:
        raise ValueError('SHA256 do ZIP não corresponde ao arquivo oficial verificado.')
    models_dir.mkdir(parents=True, exist_ok=True)
    destination = models_dir / model['id']
    if destination.exists():
        validate_model_folder(destination, model)
        return destination
    with tempfile.TemporaryDirectory(prefix='incoming_', dir=models_dir) as tmp:
        stage = Path(tmp).resolve()
        with zipfile.ZipFile(archive) as zipped:
            for entry in zipped.infolist():
                target = (stage / entry.filename).resolve()
                if (not target.is_relative_to(stage) or
                    (entry.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ValueError('ZIP com caminho ou link inseguro.')
            zipped.extractall(stage)
        candidates = list(stage.rglob('pre_processing.ini'))
        if len(candidates) != 1:
            raise ValueError('ZIP precisa conter exatamente um modelo.')
        source = candidates[0].parent
        weight = source / 'model.onnx'
        if not weight.is_file():
            raise ValueError('Peso ONNX original não encontrado.')
        (source / 'fold0').mkdir()
        shutil.move(str(weight), source / 'fold0' / 'model.onnx')
        receipt = {'model_id': model['id'], 'release': '1.2.0', 'source_url': BASE_URL + model['asset'],
                   'archive_size': model['size'], 'archive_sha256': sha256(archive),
                   'files': {str(file.relative_to(source)).replace('\\', '/'): sha256(file)
                             for file in source.rglob('*') if file.is_file()}}
        (source / 'provenance.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        validate_model_folder(source, model)
        shutil.copyfile(ROOT / 'licenses' / 'RAIDIONICS_MODELS.txt', source / 'LICENSE.txt')
        shutil.move(str(source), destination)
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', nargs='+', default=['MRI_GBM'], help='IDs do catálogo ou all')
    parser.add_argument('--models-dir', type=Path, default=ROOT / 'models')
    parser.add_argument('--cache', type=Path, default=ROOT / 'runtime' / 'downloads')
    args = parser.parse_args()
    models = MODELS if args.models == ['all'] else [get_model(name) for name in args.models]
    args.cache.mkdir(parents=True, exist_ok=True)
    for model in [BRAIN, *models]:
        if (args.models_dir / model['id']).is_dir():
            validate_model_folder(args.models_dir / model['id'], model)
            print(f"Pronto: {model['id']}", flush=True)
            continue
        archive = args.cache / model['asset']
        if not archive.is_file():
            print(f"Baixando {model['id']} ({model['size'] / 1024**2:.1f} MiB)...", flush=True)
            partial = archive.with_suffix('.partial')
            with urllib.request.urlopen(BASE_URL + model['asset'], timeout=60) as response, partial.open('wb') as handle:
                shutil.copyfileobj(response, handle)
            partial.replace(archive)
        install_archive(archive, model, args.models_dir)
        print(f"Instalado e conferido: {model['id']}", flush=True)


if __name__ == '__main__':
    main()

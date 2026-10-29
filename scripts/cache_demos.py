"""Executa demos públicas explicitamente e registra resultados persistentes.

Lê runtime/demo_sources.json, preparado com imagens e fontes verificadas.
Não baixa nem pesquisa automaticamente; nunca inclui dados no pacote de código.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from neuro_rt.service import Service, Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute-public-demos', action='store_true', required=True)
    parser.add_argument('--model', action='append')
    args = parser.parse_args()
    service = Service(Settings(ROOT))
    sources = json.loads((service.settings.data_dir / 'demo_sources.json').read_text(encoding='utf-8'))
    cache = service.settings.data_dir / 'demos.json'
    values = json.loads(cache.read_text(encoding='utf-8')) if cache.is_file() else {'schema': 'neuro-rt/demos/1', 'demos': []}
    for source in sources:
        if args.model and source['model'] not in args.model:
            continue
        file = Path(source['input_path'])
        if not file.is_file() or not file.resolve().is_relative_to(service.settings.data_dir / 'demo_inputs'):
            raise ValueError('Demo deve ser um arquivo no cache público demo_inputs.')
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        existing = next((d for d in values['demos'] if d['model'] == source['model'] and d['sha256'] == digest), None)
        if existing and source['model'] in service._demos:
            print(source['model'], 'já disponível em cache', flush=True)
            continue
        print(source['model'], 'iniciando demo pública', flush=True)
        started = time.monotonic()
        job = service.submit({'model': source['model'], 'input_path': str(file), 'device': 'auto',
                              'explicit_request': True, 'export_rtstruct': False})
        while service.job(job['id'])['status'] in ('running', 'visualizing', 'exporting'):
            time.sleep(2)
        completed = service.job(job['id'])
        if completed['status'] == 'failed':
            raise RuntimeError(f"Demo {source['model']} falhou; consulte {completed['output_dir']}.")
        if not completed['result'].get('visualization', {}).get('available'):
            raise RuntimeError('Conecte o motor de visualização do Local Suite antes de salvar a demo.')
        item = {**source, 'job_id': job['id'], 'sha256': digest,
                'elapsed_seconds': round(time.monotonic() - started, 1)}
        values['demos'] = [d for d in values['demos'] if d['model'] != source['model']] + [item]
        temporary = cache.with_suffix('.tmp')
        temporary.write_text(json.dumps(values, indent=2, ensure_ascii=False), encoding='utf-8')
        temporary.replace(cache)
        print(source['model'], completed['status'], 'cache salvo', item['elapsed_seconds'], 's', flush=True)
    service.close()


if __name__ == '__main__':
    main()

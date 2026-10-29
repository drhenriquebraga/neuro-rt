"""Shell de prova em /; não importa nem altera o projeto AUTO_CONTORNO."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from integration.radai_neuro import montar

app = FastAPI(docs_url=None, redoc_url=None)
montar(app, ROOT)


@app.get('/')
def shell():
    return HTMLResponse('''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1"><title>Prova de acoplamento NeuroRT</title>
    <style>body{margin:0;background:#07101e;color:#e6edf7;font:14px Segoe UI,sans-serif}
    header{padding:16px 30px;background:#111e32;border-bottom:1px solid #26354a}
    iframe{width:100%;height:calc(100vh - 55px);border:0}</style></head><body>
    <header>Shell de prova · módulo independente em iframe</header>
    <iframe src="/neuro/" title="NeuroRT — segmentação de SNC"
    sandbox="allow-scripts allow-same-origin allow-downloads"></iframe></body></html>''')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8768, log_level='warning')

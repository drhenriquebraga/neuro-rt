"""Local test-phase acknowledgement; no feedback or personal data is transmitted."""
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import stat
import tempfile

from neuro_rt.tool_availability import require_tool, TOOLS

VERSION = '1.1'
RECEIPT_SCHEMA = 'neuro-rt/testing-receipt/1'
TEXT = ('Esta ferramenta ainda está sendo moldada e está em fase de testes. '
        'Ao participar, você pode auxiliar o Dr. Henrique Braga com feedback de '
        'funcionalidades e relatos de erros (debugs). Nenhum feedback ou exame é '
        'enviado automaticamente. Compartilhe apenas relatos sem dados de pacientes. '
        'Os resultados são sugestões UNAPPROVED e exigem revisão no TPS.')

def policy(tool_id):
    tool = require_tool(tool_id)
    data = {'schema': 'neuro-rt/testing-policy/1', 'version': VERSION,
            'tool': tool.id, 'title': tool.title + ' · fase de testes', 'text': TEXT}
    raw = json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()
    return dict(data, digest=hashlib.sha256(raw).hexdigest())

class TestingAccess:
    """One local receipt per tool, valid for the current testing policy."""
    def __init__(self, config_dir):
        self.config_dir = Path(config_dir).absolute()

    def _receipt_path(self, tool_id):
        path = self.config_dir / f'consent-testing-{tool_id}.json'
        # Keep receipts in the installation's own configuration, like first use.
        for entry in (*reversed(path.parents), path):
            try:
                info = entry.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError('O registro de aceite não pode ser redirecionado.')
        return path

    def accept(self, tool_id, payload):
        current = policy(tool_id)
        if (not isinstance(payload, dict) or payload.get('accepted') is not True
                or payload.get('version') != current['version']
                or payload.get('digest') != current['digest']):
            raise ValueError('Confirme a participação na versão atual da fase de testes.')
        path = self._receipt_path(current['tool'])
        path.parent.mkdir(parents=True, exist_ok=True)
        value = {'schema': RECEIPT_SCHEMA, 'tool': current['tool'], 'version': current['version'],
                 'digest': current['digest'], 'accepted': True,
                 'accepted_at': datetime.now(timezone.utc).isoformat()}
        descriptor, temporary = tempfile.mkstemp(prefix='.consent-testing-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(value, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def allowed(self, _request_or_scope, tool_id):
        try:
            current = policy(tool_id)
            path = self._receipt_path(current['tool'])
            if not path.is_file():
                return False
            with path.open('rb') as stream:
                raw = stream.read(8193)
            if len(raw) > 8192:
                return False
            value = json.loads(raw)
            return (isinstance(value, dict) and value.get('schema') == RECEIPT_SCHEMA
                    and value.get('accepted') is True and value.get('tool') == current['tool']
                    and value.get('version') == current['version'] and value.get('digest') == current['digest']
                    and isinstance(value.get('accepted_at'), str) and bool(value['accepted_at']))
        except (OSError, ValueError, RecursionError):
            return False

    def require_models(self, request, model_ids, catalog):
        from fastapi import HTTPException
        accepted = {t.id for t in TOOLS if self.allowed(request, t.id)}
        for mid in model_ids:
            spec = catalog.get(mid)
            if not isinstance(spec, dict):
                continue  # The normal scientific contract reports unknown model IDs.
            groups = set(spec.get('groups', ()))
            if not groups.intersection(accepted) and not ('anatomia' in groups and accepted - {'nidus'}):
                raise HTTPException(428, 'Confirme a fase de testes da ferramenta antes de processar.')
        if not accepted:
            raise HTTPException(428, 'Confirme a fase de testes da ferramenta antes de processar.')

def page(tool_id, integrated):
    current = policy(tool_id)
    document = '''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>body{font:15px/1.6 var(--font-ui,Segoe UI,sans-serif);background:var(--bg,#101924);color:var(--text,#e4e8ef)}
dialog{max-width:620px;width:calc(100% - 48px);padding:24px;border:1px solid var(--line,#374151);border-radius:var(--r-md,8px);background:var(--panel,#172231);color:inherit}
dialog::backdrop{background:#0009}dialog h1{font-size:23px;margin-top:0}dialog label{display:flex;gap:10px;align-items:flex-start;margin:20px 0}.testing-actions{display:flex;gap:10px;flex-wrap:wrap}button,a{font:inherit}button:disabled{opacity:.5}#testing-message{min-height:1.5em}</style></head>
<body><a href="/neuro/">Voltar ao NEURO RT</a>
<dialog id="testing-dialog" aria-labelledby="testing-title" aria-describedby="testing-description">
<h1 id="testing-title">__TITLE__</h1><p id="testing-description">__TEXT__</p>
<label><input type="checkbox" id="testing-check">Compreendi e aceito participar da fase de testes.</label>
<div class="testing-actions"><button type="button" class="ui-bt pri" id="testing-accept" disabled>Participar e abrir</button>
<button type="button" class="ui-bt" id="testing-cancel">Cancelar</button></div>
<p id="testing-message" role="status" aria-live="polite"></p></dialog>
<script>(function(){'use strict';const p=__POLICY__,d=document.getElementById('testing-dialog'),c=document.getElementById('testing-check'),b=document.getElementById('testing-accept'),m=document.getElementById('testing-message');
function cancel(){location.replace('/neuro/');}document.getElementById('testing-cancel').onclick=cancel;d.addEventListener('cancel',e=>{e.preventDefault();cancel();});
c.onchange=()=>{b.disabled=!c.checked;};b.onclick=async()=>{if(!c.checked||b.disabled)return;b.disabled=true;c.disabled=true;
try{const s=await fetch('/neuro/api/testing/'+p.tool,{cache:'no-store'});if(!s.ok)throw Error();const v=await s.json();
const r=await fetch('/neuro/api/testing/'+p.tool,{method:'POST',headers:{'Content-Type':'application/json','X-Neuro-Token':v.token},body:JSON.stringify({accepted:true,version:p.version,digest:p.digest})});
if(!r.ok)throw Error();const v2=await r.json();location.assign(v2.route);}catch(_){m.textContent='Não foi possível confirmar. Tente novamente.';c.disabled=false;b.disabled=!c.checked;}};d.showModal();})();</script></body></html>'''
    title = require_tool(tool_id).display_title + ' · fase de testes'
    document = document.replace('__TITLE__', html.escape(title)).replace('__TEXT__', html.escape(current['text']))
    document = document.replace('__POLICY__', json.dumps(current, ensure_ascii=True))
    if integrated:
        import radai_menu, radai_ui
        document = radai_menu.aplicar(radai_ui.aplicar(document), 'neuro')
    return document

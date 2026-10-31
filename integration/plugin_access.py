"""Explicit first-use and test-phase guards, safe for a late plugin mount."""
import html
import json
from urllib.parse import parse_qs
from starlette.routing import BaseRoute, Match

from neuro_rt import plugin_consent
from neuro_rt.tool_availability import TOOLS, available_tools


def onboarding_page(integrated):
    current = plugin_consent.policy()
    clauses = ''.join('<p>' + html.escape(item['text']) + '</p>' for item in current['clauses'])
    page = '''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Primeiro uso · NEURO RT</title><style>
.neuro-consent{max-width:840px;margin:32px auto;padding:24px;font:15px/1.6 var(--font-ui,Segoe UI,sans-serif);color:var(--text,#e4e8ef);background:var(--panel,#172231);border:1px solid var(--line,#374151);border-radius:var(--r-md,8px)}
.neuro-consent h1{font-size:24px}.neuro-consent small{display:block;overflow-wrap:anywhere;color:var(--muted,#a5afbd)}
.neuro-consent label{display:flex;align-items:flex-start;gap:10px;margin:24px 0}.neuro-consent button{font:inherit;padding:10px 18px;border-radius:6px;cursor:pointer}.neuro-consent button:disabled{opacity:.5;cursor:default}
</style></head><body><main class="neuro-consent">
<h1>Primeiro uso do NEURO RT</h1>
<p>Leia o mesmo termo apresentado na instalação. Esta confirmação registra o primeiro uso nesta instalação da suíte.</p>
__CLAUSES__<small>Termo __VERSION__ · SHA-256 __DIGEST__</small>
<label><input type="checkbox" id="neuro-consent-check">Li e compreendi o termo do plugin e seus limites.</label>
<button type="button" class="ui-bt pri" id="neuro-consent-continue" disabled>Concordar e continuar</button>
<a class="ui-bt" href="/">Voltar à Local Suite</a>
<p id="neuro-consent-message" role="status" aria-live="polite"></p>
</main><script>
(function(){'use strict';
const check=document.getElementById('neuro-consent-check'), button=document.getElementById('neuro-consent-continue'), message=document.getElementById('neuro-consent-message');
const consent=__POLICY__;
check.addEventListener('change',function(){button.disabled=!check.checked;});
button.addEventListener('click',async function(){
 if(!check.checked || button.disabled)return; button.disabled=true;check.disabled=true;
 try{
  const status=await fetch('/neuro/api/consent',{cache:'no-store'});
  if(!status.ok)throw Error('status'); const current=await status.json();
  const response=await fetch('/neuro/api/consent',{method:'POST',headers:{'Content-Type':'application/json','X-Neuro-Token':current.token},body:JSON.stringify({accepted:true,version:consent.version,digest:consent.digest})});
  if(!response.ok)throw Error('consent'); location.replace('/neuro/');
 }catch(_){message.textContent='Não foi possível registrar o aceite. Tente novamente.';check.disabled=false;button.disabled=!check.checked;}
});})();</script></body></html>'''
    page = page.replace('__CLAUSES__', clauses).replace('__VERSION__', html.escape(current['version']))
    page = page.replace('__DIGEST__', current['digest'])
    page = page.replace('__POLICY__', json.dumps({'version': current['version'], 'digest': current['digest']}))
    if integrated:
        import radai_menu
        import radai_ui
        page = radai_menu.aplicar(radai_ui.aplicar(page), 'neuro')
    return page


class PluginAccessGate(BaseRoute):
    """A denial-only route, safe to add during the host's lazy plugin mount.

    Allowed requests return Match.NONE and use the original host/plugin route.
    No live middleware stack or FastAPI internal included-router is replaced.
    """
    def __init__(self, config_dir, integrated, authorize, testing):
        self.config_dir, self.integrated = config_dir, integrated
        self.authorize = authorize
        self.testing = testing

    def matches(self, scope):
        if scope['type'] != 'http':
            return Match.NONE, {}
        path = scope.get('path', '')
        query = parse_qs(scope.get('query_string', b'').decode('utf-8', errors='replace'))
        execution = scope.get('method') == 'POST' and (path in (
                '/neuro/api/jobs', '/neuro/api/selection', '/neuro/api/studies') or
                path.startswith('/neuro/api/studies/') and path.endswith('/retry'))
        tool = next((t for t in TOOLS if path.rstrip('/') == t.route or
                     path.rstrip('/') == '/neuro' and query.get('category', [''])[-1] == t.id), None)
        if path.rstrip('/') in ('/nidus', '/nidus/projecao') or path.startswith('/api/nidus/'):
            tool = next(t for t in TOOLS if t.id == 'nidus')
        protected = (tool is not None or execution or path.startswith('/neuro/testing/')
                     or self.integrated and path.rstrip('/') == '/neuro')
        if protected and not plugin_consent.accepted(self.config_dir, 'first_use'):
            return Match.FULL, {'neuro_access_denial': ('consent', '')}
        if tool and not self.testing.allowed(scope, tool.id):
            return Match.FULL, {'neuro_access_denial': ('testing', tool.id)}
        return Match.NONE, {}

    def url_path_for(self, name, /, **path_params):
        from starlette.routing import NoMatchFound
        raise NoMatchFound(name, path_params)

    async def handle(self, scope, receive, send):
        from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
        kind, title = scope['neuro_access_denial']
        is_api = scope.get('path', '').startswith(('/api/', '/neuro/api/'))
        if kind == 'testing':
            response = (JSONResponse({'detail': 'Confirme a participação na fase de testes.',
                'onboarding': '/neuro/testing/' + title}, status_code=428) if is_api else
                RedirectResponse('/neuro/testing/' + title, status_code=303))
        else:
            response = (JSONResponse({'detail': 'Confirme o termo no primeiro uso do NEURO RT.',
                                      'onboarding': '/neuro/onboarding'}, status_code=428)
                        if is_api else RedirectResponse('/neuro/onboarding', status_code=303))
        response.headers['Cache-Control'] = 'no-store'
        return await response(scope, receive, send)


def attach(app, router, service, config_dir, local, action, *, integrated):
    from fastapi import HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from integration.testing_access import TestingAccess, policy as testing_policy, page as testing_page
    testing = TestingAccess()
    service.testing_access = testing

    @router.get('/testing/{tool_id}')
    def testing_entry(request: Request, tool_id: str):
        local(request)
        try:
            return HTMLResponse(testing_page(tool_id, integrated), headers={'Cache-Control': 'no-store'})
        except ValueError as exc:
            raise HTTPException(404, 'Ferramenta desconhecida.') from exc

    @router.get('/api/testing/{tool_id}')
    def testing_status(request: Request, tool_id: str):
        local(request)
        try:
            return JSONResponse({'policy': testing_policy(tool_id), 'token': service.token},
                                headers={'Cache-Control': 'no-store'})
        except ValueError as exc:
            raise HTTPException(404, 'Ferramenta desconhecida.') from exc

    @router.post('/api/testing/{tool_id}')
    async def testing_accept(request: Request, tool_id: str):
        from neuro_rt.tool_availability import require_tool
        payload = await action(request, 8192)
        if not plugin_consent.accepted(config_dir, 'first_use'):
            raise HTTPException(428, 'Confirme o termo no primeiro uso do NEURO RT.')
        try:
            tool = require_tool(tool_id)
            nonce = testing.accept(tool_id, payload)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        response = JSONResponse({'route': tool.route}, headers={'Cache-Control': 'no-store'})
        response.set_cookie('neuro_testing_' + tool_id, nonce, max_age=8*3600,
                            httponly=True, samesite='strict', path='/')
        return response

    @router.get('/onboarding')
    def onboarding(request: Request):
        local(request)
        return HTMLResponse(onboarding_page(integrated), headers={'Cache-Control': 'no-store'})

    @router.get('/api/consent')
    def consent_status(request: Request):
        local(request)
        return JSONResponse({'policy': plugin_consent.policy(), 'token': service.token,
            'installation': plugin_consent.accepted(config_dir, 'installation'),
            'first_use': plugin_consent.accepted(config_dir, 'first_use'),
            'tools': available_tools()}, headers={'Cache-Control': 'no-store'})

    @router.post('/api/consent')
    async def acknowledge(request: Request):
        payload = await action(request, 8192)
        try:
            receipt = plugin_consent.accept(config_dir, 'first_use', payload)
        except (OSError, ValueError) as exc:
            raise HTTPException(400, 'Aceite atual ausente ou não pôde ser gravado.') from exc
        return JSONResponse(receipt, headers={'Cache-Control': 'no-store'})

    def authorize(request):
        local(request)
        if (request.headers.get('origin') not in (None, f'{request.url.scheme}://{request.url.netloc}')
                or request.headers.get('x-neuro-token') != service.token):
            raise HTTPException(403, 'Origem ou token inválido.')

    def protect_routes():
        # A public Starlette route supports both old FastAPI flat routes and new
        # included routers. It can be registered after startup, unlike middleware.
        if not any(isinstance(route, PluginAccessGate) for route in app.router.routes):
            app.router.routes.insert(0, PluginAccessGate(config_dir, integrated, authorize, testing))
    return protect_routes

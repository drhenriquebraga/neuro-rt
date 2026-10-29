"""Único arquivo de conexão a importar pelo servidor do Local Suite."""
from pathlib import Path
import sys


def montar(app, module_root, *, host_services=None):
    from fastapi import APIRouter, HTTPException, Request
    from fastapi.responses import FileResponse, RedirectResponse, JSONResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from starlette.concurrency import run_in_threadpool

    root = Path(module_root).resolve()
    sys.path.insert(0, str(root))
    from neuro_rt.service import Service, Settings

    if hasattr(app.state, 'neuro_rt'):
        return app.state.neuro_rt
    plugin_paths = None
    if host_services is not None:
        from neuro_rt.plugin_paths import resolve_plugin_paths
        import json
        host_root = Path(host_services.host_info['suite_root']).resolve()
        state_file = host_root / 'Plugins/NEURO RT/installation.json'
        if state_file.is_file():
            plugin_paths = resolve_plugin_paths(host_root, json.loads(state_file.read_text(encoding='utf-8')))
            if plugin_paths.code_dir != root:
                raise ValueError('O código montado não corresponde à versão ativa do plugin.')
    settings = Settings(root, plugin_paths=plugin_paths)
    if host_services is not None:
        settings.host_app = Path(host_services.host_info['suite_root']).resolve()
        embedded = settings.host_app / 'python/python.exe'
        development = settings.host_app / '.venv/Scripts/python.exe'
        configured = Path(settings.host_python)
        settings.host_python = str(embedded if embedded.is_file() else
            configured if plugin_paths is None and configured.is_file() else development)
    service = Service(settings, host_services=host_services)
    router = APIRouter(prefix='/neuro')

    def local(request):
        if not request.client or request.client.host not in ('127.0.0.1', '::1', 'localhost', 'testclient'):
            raise HTTPException(403, 'NeuroRT aceita somente conexões locais.')
        allowed = ('127.0.0.1', '::1', 'localhost')
        if request.client.host == 'testclient':
            allowed += ('testserver',)
        if request.url.hostname not in allowed:
            raise HTTPException(403, 'Host não permitido.')
        if request.headers.get('sec-fetch-site') == 'cross-site':
            raise HTTPException(403, 'Origem não permitida.')

    async def action(request, maximum=524288):
        local(request)
        origin = request.headers.get('origin')
        if (origin not in (None, f'{request.url.scheme}://{request.url.netloc}') or
                request.headers.get('x-neuro-token') != service.token):
            raise HTTPException(403, 'Origem ou token inválido.')
        body = await request.body()
        if not 0 < len(body) <= maximum: raise HTTPException(400, 'Pedido JSON inválido.')
        try:
            value = await request.json()
            if not isinstance(value, dict): raise ValueError()
            return value
        except (ValueError, UnicodeError):
            raise HTTPException(400, 'Pedido JSON inválido.')

    def studies():
        if service.studies is None:
            raise HTTPException(409, 'Este fluxo requer integração com o Local Suite.')
        return service.studies

    def fail(exc):
        if isinstance(exc, (KeyError, FileNotFoundError)):
            return HTTPException(404, 'Resultado não encontrado.')
        if isinstance(exc, RuntimeError):
            return HTTPException(409, str(exc))
        return HTTPException(400, str(exc))

    if host_services is None:
        @router.get('')
        def redirect():
            return RedirectResponse('/neuro/')

    @router.get('/api/status')
    def status(request: Request):
        local(request)
        return JSONResponse(service.status(), headers={'Cache-Control': 'no-store'})

    @router.post('/api/selection')
    async def selection(request: Request):
        body = await action(request)
        try:
            value = await run_in_threadpool(studies().selection, body.get('tickets'), body.get('category'))
            return JSONResponse(value, headers={'Cache-Control': 'no-store'})
        except (KeyError, ValueError, RuntimeError, TypeError) as exc:
            raise fail(exc)

    @router.post('/api/studies', status_code=202)
    async def submit_study(request: Request):
        body = await action(request)
        try:
            value = await run_in_threadpool(studies().submit, body)
            return JSONResponse(value, status_code=202, headers={'Cache-Control': 'no-store'})
        except (KeyError, ValueError, RuntimeError, TypeError) as exc:
            raise fail(exc)

    @router.get('/api/studies')
    def list_studies(request: Request):
        local(request)
        return JSONResponse({'studies': studies().list_jobs(),
            'results': studies().store.list_results(all_revisions=True)}, headers={'Cache-Control': 'no-store'})

    @router.get('/api/studies/{study_id}')
    def study(request: Request, study_id: str, revision: int = None):
        local(request)
        try: return JSONResponse(studies().job(study_id, revision), headers={'Cache-Control': 'no-store'})
        except (KeyError, ValueError, FileNotFoundError) as exc: raise fail(exc)

    @router.post('/api/studies/{study_id}/retry', status_code=202)
    async def retry_study(request: Request, study_id: str):
        body = await action(request, 4096)
        try:
            result = await run_in_threadpool(studies().retry, study_id,
                                            explicit_request=body.get('explicit_request'))
            return JSONResponse(result, status_code=202, headers={'Cache-Control': 'no-store'})
        except (KeyError, ValueError, RuntimeError, FileNotFoundError) as exc: raise fail(exc)

    @router.post('/api/studies/{study_id}/cancel')
    async def cancel_study(request: Request, study_id: str):
        await action(request, 4096)
        try: return JSONResponse(studies().cancel(study_id), headers={'Cache-Control': 'no-store'})
        except KeyError as exc: raise fail(exc)

    @router.get('/api/studies/{study_id}/artifacts/{artifact_id}')
    def study_artifact(request: Request, study_id: str, artifact_id: str):
        local(request)
        try:
            artifact = studies().store.resolve_artifact(study_id, artifact_id)
            return FileResponse(artifact.path, media_type=artifact.media_type,
                filename=artifact.path.name, headers={'Cache-Control': 'no-store'})
        except (KeyError, ValueError, FileNotFoundError) as exc: raise fail(exc)

    if host_services is not None:
        @router.get('/')
        def integrated_page(request: Request, category: str = ''):
            local(request)
            from integration.radai_neuro_screen import pagina_neuro, pagina_estudo
            try:
                page = (pagina_estudo(category, host_services) if category else
                        pagina_neuro(host_services, {'state': 'ready'}))
                return HTMLResponse(page, headers={'Cache-Control': 'no-store'})
            except ValueError as exc: raise fail(exc)

    @router.get('/api/series')
    def series(request: Request, path: str):
        local(request)
        if host_services is not None:
            raise HTTPException(400, 'Use o carregador de séries do Local Suite.')
        from neuro_rt.imaging import dicom_series
        if not Path(path).is_dir():
            raise HTTPException(400, 'Informe uma pasta DICOM existente.')
        try:
            return {'series': dicom_series(path)}
        except ValueError as exc:
            raise fail(exc)

    @router.get('/api/demos/{model}')
    def demo(request: Request, model: str):
        local(request)
        try:
            return service.demo(model)
        except (KeyError, ValueError) as exc:
            raise fail(exc)

    @router.post('/api/jobs', status_code=202)
    async def submit(request: Request):
        local(request)
        origin = request.headers.get('origin')
        if (origin not in (None, f'{request.url.scheme}://{request.url.netloc}') or
            request.headers.get('x-neuro-token') != service.token):
            raise HTTPException(403, 'Origem ou token inválido.')
        body = await request.body()
        if not 0 < len(body) <= 16384:
            raise HTTPException(400, 'Pedido JSON inválido.')
        try:
            return await run_in_threadpool(service.submit, await request.json())
        except (ValueError, RuntimeError, TypeError) as exc:
            raise fail(exc)

    @router.get('/api/jobs/{job_id}')
    def job(request: Request, job_id: str):
        local(request)
        try:
            return service.job(job_id)
        except KeyError as exc:
            raise fail(exc)

    @router.get('/api/jobs/{job_id}/artifacts/{name}')
    def artifact(request: Request, job_id: str, name: str):
        local(request)
        try:
            return FileResponse(service.artifact(job_id, name), filename=name,
                                headers={'Cache-Control': 'no-store'})
        except (KeyError, ValueError, FileNotFoundError) as exc:
            raise fail(exc)

    @router.get('/api/jobs/{job_id}/views/{name}')
    def view(request:Request,job_id:str,name:str):
        local(request)
        try:return FileResponse(service.view_file(job_id,name),headers={'Cache-Control':'no-store'})
        except (KeyError,ValueError,FileNotFoundError) as exc:raise fail(exc)

    app.include_router(router)
    app.mount('/neuro/', StaticFiles(directory=str(root / 'web'), html=True), name='neuro-rt-web')
    if host_services is not None:
        from integration.nidus_bridge import montar as montar_nidus
        montar_nidus(app, host_services)
    app.router.add_event_handler('shutdown', service.close)
    app.state.neuro_rt = service
    return service

"""Único arquivo de conexão a importar pelo servidor do Local Suite."""
from pathlib import Path
import sys


def montar(app, module_root):
    from fastapi import APIRouter, HTTPException, Request
    from fastapi.responses import FileResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    from starlette.concurrency import run_in_threadpool

    root = Path(module_root).resolve()
    sys.path.insert(0, str(root))
    from neuro_rt.service import Service, Settings

    if hasattr(app.state, 'neuro_rt'):
        return app.state.neuro_rt
    service = Service(Settings(root))
    router = APIRouter(prefix='/neuro')

    def local(request):
        if not request.client or request.client.host not in ('127.0.0.1', '::1', 'localhost', 'testclient'):
            raise HTTPException(403, 'NeuroRT aceita somente conexões locais.')
        allowed = ('127.0.0.1', '::1', 'localhost')
        if request.client.host == 'testclient':
            allowed += ('testserver',)
        if request.url.hostname not in allowed:
            raise HTTPException(403, 'Host não permitido.')

    def fail(exc):
        if isinstance(exc, (KeyError, FileNotFoundError)):
            return HTTPException(404, 'Resultado não encontrado.')
        if isinstance(exc, RuntimeError):
            return HTTPException(409, str(exc))
        return HTTPException(400, str(exc))

    @router.get('')
    def redirect():
        return RedirectResponse('/neuro/')

    @router.get('/api/status')
    def status(request: Request):
        local(request)
        return service.status()

    @router.get('/api/series')
    def series(request: Request, path: str):
        local(request)
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
    app.router.add_event_handler('shutdown', service.close)
    app.state.neuro_rt = service
    return service

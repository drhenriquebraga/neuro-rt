"""Nidus-only manual consensus actions, sharing host authorization and queue."""
import secrets
import threading
import uuid
from urllib.parse import urlencode


def attach_consensus_api(app, sessions, resolve_source):
    from fastapi import HTTPException, Request
    from fastapi.responses import FileResponse, JSONResponse
    from starlette.concurrency import run_in_threadpool
    from neuro_rt.nidus_geometry import NidusCandidate, export_candidate

    def local(request):
        allowed = ('127.0.0.1', '::1', 'localhost', 'testclient')
        if not request.client or request.client.host not in allowed:
            raise HTTPException(403, 'Acesso local obrigatório.')
        hosts = ('127.0.0.1', '::1', 'localhost') + (('testserver',) if request.client.host == 'testclient' else ())
        if request.url.hostname not in hosts or request.headers.get('sec-fetch-site') == 'cross-site':
            raise HTTPException(403, 'Origem não permitida.')

    async def body(request, fields):
        local(request)
        service = getattr(app.state, 'neuro_rt', None)
        if (service is None or not secrets.compare_digest(request.headers.get('x-neuro-token', ''), service.token)
                or request.headers.get('origin') not in (None, str(request.base_url).rstrip('/'))):
            raise HTTPException(403, 'Origem ou token inválido.')
        raw = await request.body()
        if not 0 < len(raw) <= 16384:
            raise HTTPException(400, 'Pedido de consenso inválido.')
        try:
            value = await request.json()
            if not isinstance(value, dict) or set(value) != set(fields):
                raise ValueError()
        except (ValueError, UnicodeError):
            raise HTTPException(400, 'Pedido de consenso inválido.') from None
        return value, service

    def session(identity):
        if not isinstance(identity, str) or identity not in sessions:
            raise HTTPException(404, 'As incidências expiraram; grave-as novamente.')
        value = sessions[identity]
        if value.get('consenso') is None:
            raise HTTPException(409, 'Registre as incidências antes de ajustar o consenso.')
        value.setdefault('consenso_lock', threading.RLock())
        return value

    def folder(service, candidate):
        return service.settings.data_dir / 'nidus' / candidate.id

    def queued(value, service, operation, callback):
        bridge = service.host_services.queue_bridge
        if bridge is None:
            raise ValueError('A fila compartilhada da suíte está indisponível.')
        request_id = uuid.uuid4().hex
        ticket = bridge.enqueue_study(request_id, {'study_id': 'nidus-' + request_id, 'reference': value['b']})
        with bridge.await_turn(ticket):
            def checkpoint(fraction=None):
                if bridge.cancelled(ticket):
                    raise RuntimeError('Operação Nidus cancelada pela fila.')
                bridge.report(ticket, {'stage': operation, 'fraction': 0. if fraction is None else fraction})
            checkpoint()
            result = callback(checkpoint)
            bridge.report(ticket, {'stage': operation, 'fraction': 1.})
            return result

    async def perform(call):
        try:
            result = await run_in_threadpool(call)
            return JSONResponse(result, headers={'Cache-Control': 'no-store'})
        except HTTPException:
            raise
        except (ValueError, RuntimeError):
            raise HTTPException(409, 'Não foi possível concluir. Confira a referência, o contorno e a fila da suíte.') from None
        except OSError:
            raise HTTPException(409, 'Não foi possível gravar o resultado; o contorno anterior foi preservado.') from None

    @app.post('/api/nidus/consenso')
    async def prepare(request: Request):
        data, service = await body(request, ('s', 'temperatura'))
        value = session(data['s'])
        def run():
            def calculate(checkpoint):
                candidate = NidusCandidate(value['consenso'], data['temperatura'], progress=checkpoint)
                with value['consenso_lock']:
                    candidate.save(folder(service, candidate), checkpoint=checkpoint)
                    value['candidato'] = candidate
                return candidate.metadata()
            return queued(value, service, 'running', calculate)
        return await perform(run)

    @app.post('/api/nidus/consenso/editar')
    async def edit(request: Request):
        data, service = await body(request, ('s', 'eixo', 'indice', 'pontos', 'operacao'))
        value = session(data['s'])
        def run():
            def calculate(checkpoint):
                with value['consenso_lock']:
                    candidate = value.get('candidato')
                    if candidate is None:
                        raise ValueError('Prepare a sugestão antes de editar.')
                    candidate = candidate.fork()
                    candidate.edit(data['eixo'], data['indice'], data['pontos'], data['operacao'])
                    candidate.save(folder(service, candidate), checkpoint=checkpoint)
                    value['candidato'] = candidate
                    return candidate.metadata()
            return queued(value, service, 'running', calculate)
        return await perform(run)

    @app.post('/api/nidus/consenso/desfazer')
    async def undo(request: Request):
        data, service = await body(request, ('s',))
        value = session(data['s'])
        def run():
            def calculate(checkpoint):
                with value['consenso_lock']:
                    candidate = value.get('candidato')
                    if candidate is None:
                        raise ValueError('Sem contorno editável.')
                    candidate = candidate.fork()
                    candidate.undo()
                    candidate.save(folder(service, candidate), checkpoint=checkpoint)
                    value['candidato'] = candidate
                    return candidate.metadata()
            return queued(value, service, 'running', calculate)
        return await perform(run)

    @app.post('/api/nidus/consenso/exportar')
    async def export(request: Request):
        data, service = await body(request, ('s', 'temperatura', 'editado'))
        value = session(data['s'])
        if type(data['editado']) is not bool:
            raise HTTPException(400, 'Escolha de contorno inválida.')
        def run():
            def calculate(checkpoint):
                with value['consenso_lock']:
                    candidate = value.get('candidato') if data['editado'] else None
                    if data['editado'] and candidate is None:
                        raise ValueError('O contorno editado não está mais disponível; prepare-o novamente.')
                    if candidate is None:
                        candidate = NidusCandidate(value['consenso'], data['temperatura'], progress=checkpoint)
                        candidate.save(folder(service, candidate), checkpoint=checkpoint)
                    source, uid = resolve_source(value['b'])
                    if not source or not uid or not value.get('source_signature'):
                        raise ValueError('Referência indisponível.')
                    file = export_candidate(candidate, source, uid, service.settings.host_app,
                        folder(service, candidate), checkpoint=lambda: checkpoint(),
                        expected_signature=value['source_signature'])
                    artifact = uuid.uuid4().hex
                    value.setdefault('exportacoes', {})[artifact] = file
                    return {'url': '/api/nidus/consenso/download?' + urlencode({'s': data['s'], 'id': artifact}),
                            'approval_status': 'UNAPPROVED', 'revision': candidate.revision}
            return queued(value, service, 'exporting', calculate)
        return await perform(run)

    @app.get('/api/nidus/consenso/download')
    def download(request: Request, s: str = '', id: str = ''):
        local(request)
        value = session(s)
        file = value.get('exportacoes', {}).get(id)
        if file is None or not file.is_file():
            raise HTTPException(404, 'Arquivo de contorno não encontrado.')
        return FileResponse(file, media_type='application/dicom', filename='RS_Nidus_Sugestao.dcm',
                            headers={'Cache-Control': 'no-store'})

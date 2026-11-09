"""Nidus-only manual consensus actions, sharing host authorization and queue."""
import secrets
from pathlib import Path
import tempfile
import threading
import uuid
from urllib.parse import urlencode


def attach_consensus_api(app, sessions, resolve_source):
    from fastapi import HTTPException, Request
    from fastapi.responses import FileResponse, JSONResponse
    from starlette.concurrency import run_in_threadpool
    from neuro_rt.nidus_geometry import NidusCandidate, export_candidate, source_signature
    from neuro_rt.series_selection import describe_series

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

    async def perform(call, status_code=200):
        try:
            result = await run_in_threadpool(call)
            return JSONResponse(result, status_code=status_code, headers={'Cache-Control': 'no-store'})
        except HTTPException:
            raise
        except (ValueError, RuntimeError):
            raise HTTPException(409, 'Não foi possível concluir. Confira a referência, o contorno e a fila da suíte.') from None
        except OSError:
            raise HTTPException(409, 'Não foi possível gravar o resultado; o contorno anterior foi preservado.') from None

    def require_nidus_studies(request, service):
        if not service.testing_access.allowed(request, 'nidus'):
            raise HTTPException(428, 'Confirme a fase de testes do Nidus RT antes de processar.')
        if service.studies is None:
            raise HTTPException(409, 'A entrega conjunta requer integração com a fila da suíte.')
        return service.studies

    @app.post('/api/nidus/consenso/anatomia')
    async def anatomy(request: Request):
        data, service = await body(request, ('s', 'bilhetes'))
        studies = require_nidus_studies(request, service)
        value = session(data['s'])
        tickets = data['bilhetes']
        if (not isinstance(tickets, list) or len(tickets) > 119
                or any(not isinstance(ticket, str) or not 0 < len(ticket) <= 160 for ticket in tickets)):
            raise HTTPException(400, 'Lista de séries para Anatomia inválida.')

        def run():
            ref = describe_series(value['b'], service.host_services)
            compatible = [ref.ticket]
            for ticket in dict.fromkeys(tickets):
                if ticket == ref.ticket:
                    continue
                try:
                    series = describe_series(ticket, service.host_services)
                except (ValueError, OSError):
                    continue  # Other results in a previously loaded list may have expired.
                if (series.subject_key, series.study_key, series.modality, series.source_format) == (
                        ref.subject_key, ref.study_key, ref.modality, 'dicom'):
                    compatible.append(ticket)
            result = studies.selection(compatible, 'anatomia')
            models = [model for model in result['models']
                      if 'anatomia' in model['groups']]
            token = uuid.uuid4().hex
            with value['consenso_lock']:
                value['anatomia'] = (token, {m['id']: m['bindings'] for m in models
                                            if m['eligibility']['selectable']})
            return {'selection': token, 'models': models, 'reference': ref.ticket}

        return await perform(run)

    @app.post('/api/nidus/consenso/exportar-com-anatomia')
    async def export_with_anatomy(request: Request):
        data, service = await body(request, ('s', 'temperatura', 'editado', 'selection', 'modelos'))
        studies = require_nidus_studies(request, service)
        value = session(data['s'])
        models = data['modelos']
        if (type(data['editado']) is not bool or not isinstance(data['selection'], str)
                or not isinstance(models, list) or not 0 < len(models) <= 16
                or any(not isinstance(model, str) for model in models) or len(set(models)) != len(models)):
            raise HTTPException(400, 'Escolha de contorno ou de modelos inválida.')

        def run():
            import SimpleITK as sitk

            snapshot_dir = service.settings.data_dir / 'nidus'
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='combined-', dir=snapshot_dir) as temporary:
                mask_path = Path(temporary).resolve() / 'mask.nii.gz'

                def calculate(checkpoint):
                    with value['consenso_lock']:
                        token, bindings = value.get('anatomia', (None, {}))
                        if data['selection'] != token or any(model not in bindings for model in models):
                            raise HTTPException(409, 'Atualize a seleção de Anatomia para esta referência.')
                        candidate = value.get('candidato') if data['editado'] else None
                        if data['editado'] and candidate is None:
                            raise ValueError('O contorno editado não está mais disponível.')
                        if candidate is None:
                            candidate = NidusCandidate(value['consenso'], data['temperatura'], progress=checkpoint)
                        source, uid = resolve_source(value['b'])
                        signature = value.get('source_signature')
                        if not source or not uid or not signature or source_signature(source, uid) != signature:
                            raise ValueError('A referência original mudou desde a gravação das incidências.')
                        mask = candidate.mask()
                        geometry = candidate.geometry
                        if mask.shape != tuple(reversed(geometry['size'])) or not mask.any():
                            raise ValueError('O consenso está vazio ou fora da geometria da referência.')
                        image = sitk.GetImageFromArray(mask.astype('uint8'))
                        image.SetSpacing(geometry['spacing'])
                        image.SetOrigin(geometry['origin'])
                        image.SetDirection(geometry['direction'])
                        sitk.WriteImage(image, str(mask_path))
                        checkpoint()
                        return candidate.revision, signature, {model: bindings[model] for model in models}

                revision, signature, bindings = queued(value, service, 'preparing', calculate)
                study_id = uuid.uuid4().hex
                studies.submit({'schema': 'neuro-rt/request/2', 'request_id': uuid.uuid4().hex,
                    'explicit_request': True, 'export_rtstruct': True, 'studies': [{
                        'study_id': study_id, 'reference': value['b'], 'model_ids': models,
                        'bindings_by_model': bindings}]}, nidus_snapshot={'mask_path': str(mask_path),
                            'revision': revision, 'source_signature': signature})
                return {'study_id': study_id, 'revision': revision, 'approval_status': 'UNAPPROVED'}

        return await perform(run, status_code=202)

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

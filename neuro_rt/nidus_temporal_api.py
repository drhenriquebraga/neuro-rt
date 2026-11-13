"""Bounded, cancellable temporal preview jobs. No segmentation/export side effects."""
from collections import OrderedDict
from dataclasses import dataclass, field
import io
import json
import math
import queue
import secrets
import threading
import time

import numpy as np
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from . import nidus_temporal as temporal

PREFIX = '/api/nidus/temporal'
_TERMINAL = ('ready', 'failed', 'cancelled')
_MESSAGE = {
    'INVALID_REQUEST': 'Pedido de CINE inválido.',
    'INVALID_VIEW': 'Parâmetros de reconstrução inválidos.',
    'UNKNOWN_GROUP': 'Selecione novamente o grupo temporal.',
    'UNKNOWN_JOB': 'O preparo expirou. Prepare o CINE novamente.',
    'UNKNOWN_TICKET': 'Selecione novamente as séries no arquivo local.',
    'SOURCE_CHANGED': 'A série mudou durante o preparo. Recarregue o exame.',
    'RESOURCE_LIMIT': 'O CINE excede o limite de memória ou de fases desta estação.',
    'TIMEOUT': 'O preparo excedeu o tempo disponível. Selecione um grupo menor.',
    'NOT_READY': 'Os quadros reais ainda estão sendo preparados.',
    'CANCELLED': 'Preparo cancelado.',
    'PIXEL_DECODE_FAILED': 'Não foi possível decodificar os pixels desta série.',
    'INDEXED_MULTIFRAME_READER_REQUIRED': 'Atualize o programa para abrir este DICOM multiframe.',
    'PROCESSING_FAILED': 'Não foi possível preparar este grupo temporal.',
}


def _error(code):
    return {'code': code, 'message': _MESSAGE.get(code, 'O grupo não possui dados temporais e geometria compatíveis.')}


def _view(body, kind):
    allowed = {'group', 'lao', 'cra', 'modo', 'janela', 'lado', 'laje', 'caixa'}
    if not isinstance(body, dict) or set(body) - allowed:
        raise temporal.TemporalError('INVALID_REQUEST')
    try:
        lao, cra = float(body.get('lao', 0)), float(body.get('cra', 0))
        laje = float(body.get('laje') or 0)
        lado = body.get('lado', 1024)
        modo, janela = body.get('modo', 'mip'), body.get('janela', 'angio')
        if (any(not math.isfinite(x) for x in (lao, cra, laje)) or
                not -180 <= lao <= 180 or not -90 <= cra <= 90 or not 0 <= laje <= 1000 or
                lado != 1024 or modo not in ('mip', 'minip') or
                janela not in ('angio', 'vaso_fino', 'osso', 'parenquima')):
            raise ValueError()
        caixa = body.get('caixa')
        if caixa is not None:
            if not isinstance(caixa, list) or len(caixa) != 6:
                raise ValueError()
            caixa = tuple(float(x) for x in caixa)
            if (any(not math.isfinite(x) or not 0 <= x <= 1 for x in caixa) or
                    any(caixa[i] >= caixa[i + 1] for i in (0, 2, 4))):
                raise ValueError()
        if kind == 'projection2d' and (lao or cra or laje or caixa is not None):
            raise ValueError()
    except (TypeError, ValueError, OverflowError):
        raise temporal.TemporalError('INVALID_VIEW') from None
    return {'lao': lao, 'cra': cra, 'modo': modo, 'janela': janela, 'lado': 1024,
            'laje': laje or None, 'caixa': caixa}


def render_frame(data, params, scale):
    """Same projector as static NIDUS, under its lock, with a group-wide window."""
    import radai_nidus as N
    if data.array.ndim == 2:
        from PIL import Image
        center, width = N.janela_de(params['janela'], scale)
        array = N.para_a_tela(data.array, data.spacing[1], data.spacing[0])
        pixels = np.clip((array - (center - width / 2)) * (255. / max(width, 1e-6)), 0, 255).astype(np.uint8)
        if data.mono1:
            pixels = 255 - pixels
        # Retain the acquired 2-D image; no invented camera rotation or 3-D volume.
        image = Image.fromarray(pixels)
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue(), {'center': center, 'width': width}
    import radai_recon3d as R
    image = data.image()
    sample = None
    if params['caixa'] is not None:
        series = N.abrir(image, 'MR')
        series.escala = scale
        sample = series.img_na_caixa(params['caixa'], params['modo'], False)
    plane, info = N.projetar(image, params['lao'], params['cra'], params['modo'], params['janela'],
                            lado=1024, laje_mm=params['laje'], escala=scale, amostra=sample)
    return R.para_png(plane, info['centro'], info['largura']), {'center': info['centro'], 'width': info['largura']}


@dataclass
class Job:
    group: temporal.Group
    params: dict
    id: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    state: str = 'queued'
    completed: int = 0
    pngs: dict = field(default_factory=dict, repr=False)
    window: dict | None = None
    error: dict | None = None
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    touched: float = field(default_factory=time.monotonic)
    started: float = 0


class TemporalService:
    def __init__(self, resolver, projection_lock, renderer=None):
        if projection_lock is None:
            raise ValueError('The shared NIDUS projection lock is required')
        self.resolver, self.projection_lock = resolver, projection_lock
        self.renderer = renderer or render_frame
        self.max_png_bytes = 128 * 1024 * 1024
        self.max_seconds, self.ttl = 900., 600.
        self.max_groups, self.max_jobs = 8, 3
        self.groups, self.jobs = OrderedDict(), OrderedDict()
        self.lock = threading.RLock()
        self.pending = queue.Queue(maxsize=self.max_jobs)
        self.closed = threading.Event()
        self.worker = threading.Thread(target=self._work, name='nidus-temporal-preview', daemon=True)
        self.worker.start()

    def close(self):
        self.closed.set()
        with self.lock:
            for job in self.jobs.values():
                job.cancel.set()
                job.pngs.clear()
        self.worker.join(timeout=5)

    def _reap(self):
        now = time.monotonic()
        for key, (_, touched) in list(self.groups.items()):
            if now - touched > self.ttl:
                self.groups.pop(key, None)
        for key, job in list(self.jobs.items()):
            if now - job.touched > self.ttl:
                job.cancel.set()
                job.pngs.clear()
                self.jobs.pop(key, None)

    def _resolve(self, row):
        if (not isinstance(row, dict) or set(row) - {'bilhete', 'origem'} or
                not isinstance(row.get('bilhete'), str) or not 1 <= len(row['bilhete']) <= 256 or
                row.get('origem', 'pasta') not in ('pasta', 'acervo')):
            raise temporal.TemporalError('INVALID_REQUEST')
        try:
            folder, uid = self.resolver(row['bilhete'], row.get('origem', 'pasta'))
        except Exception:
            raise temporal.TemporalError('UNKNOWN_TICKET') from None
        if not folder or not uid:
            raise temporal.TemporalError('UNKNOWN_TICKET')
        return {'folder': str(folder), 'uid': str(uid)}

    def discover(self, body):
        if (not isinstance(body, dict) or set(body) - {'itens', 'ancora'} or
                not isinstance(body.get('itens'), list) or not 1 <= len(body['itens']) <= 128):
            raise temporal.TemporalError('INVALID_REQUEST')
        sources = [self._resolve(row) for row in body['itens']]
        anchor = None
        if body.get('ancora') is not None:
            source = self._resolve(body['ancora'])
            anchor = temporal.source_identity(source['folder'], source['uid'])
            if anchor is None:
                raise temporal.TemporalError('UNKNOWN_TICKET')
        result = temporal.discover(sources, anchor_identity=anchor)
        with self.lock:
            self._reap()
            for group in result.groups[:self.max_groups]:
                self.groups[group.id] = (group, time.monotonic())
            while len(self.groups) > self.max_groups:
                self.groups.popitem(last=False)
        return {'groups': [g.public() for g in result.groups[:self.max_groups]], 'rejected': result.rejected}

    def prepare(self, body):
        if not isinstance(body, dict) or not isinstance(body.get('group'), str):
            raise temporal.TemporalError('INVALID_REQUEST')
        with self.lock:
            self._reap()
            entry = self.groups.get(body['group'])
            if entry is None:
                raise temporal.TemporalError('UNKNOWN_GROUP')
            group = entry[0]
            params = _view(body, group.kind)
            # Identical completed requests reuse real PNGs, never redecode a CINE loop.
            for existing in self.jobs.values():
                if existing.group.id == group.id and existing.params == params and existing.state not in ('failed', 'cancelled'):
                    existing.touched = time.monotonic()
                    return self.status(existing.id)
            while len(self.jobs) >= self.max_jobs:
                oldest = next((key for key, job in self.jobs.items() if job.state in _TERMINAL), None)
                if oldest is None:
                    raise temporal.TemporalError('RESOURCE_LIMIT')
                self.jobs.pop(oldest).pngs.clear()
            job = Job(group, params)
            self.jobs[job.id] = job
            self.groups[group.id] = (group, time.monotonic())
            try:
                self.pending.put_nowait(job)
            except queue.Full:
                self.jobs.pop(job.id, None)
                raise temporal.TemporalError('RESOURCE_LIMIT') from None
            return self.status(job.id)

    def _get(self, key):
        self._reap()
        job = self.jobs.get(key)
        if job is None:
            raise temporal.TemporalError('UNKNOWN_JOB')
        job.touched = time.monotonic()
        if job.group.id in self.groups:
            self.groups[job.group.id] = (job.group, job.touched)
        return job

    def status(self, key):
        with self.lock:
            job = self._get(key)
            public = job.group.public()
            return {'job': job.id, 'state': job.state, 'completed': job.completed,
                    'total': 2 * len(job.group.frames), 'count': len(job.group.frames),
                    'ready_count': len(job.pngs), 'first_ready': 0 in job.pngs,
                    'can_play': job.state == 'ready', 'error': job.error,
                    'kind': public['kind'], 'can_rotate': public['can_rotate'],
                    'frames': public['frames'], 'timing_known': public['timing_known'], 'window': job.window}

    def frame(self, key, index):
        with self.lock:
            job = self._get(key)
            if job.state in ('failed', 'cancelled') or index not in job.pngs:
                raise temporal.TemporalError('NOT_READY')
            return job.pngs[index]

    def cancel(self, key):
        with self.lock:
            job = self._get(key)
            job.cancel.set()
            job.state = 'cancelled'
            job.pngs.clear()
            return self.status(key)

    def _check(self, job):
        if self.closed.is_set() or job.cancel.is_set():
            raise temporal.TemporalError('CANCELLED')
        if time.monotonic() - job.started > self.max_seconds:
            raise temporal.TemporalError('TIMEOUT')

    def _acquire_projection(self, job):
        # Cancellation also works while the static renderer holds the shared lock.
        while not self.projection_lock.acquire(timeout=.2):
            self._check(job)
        try:
            self._check(job)
        except Exception:
            self.projection_lock.release()
            raise

    def _work(self):
        while not self.closed.is_set():
            try:
                job = self.pending.get(timeout=.5)
            except queue.Empty:
                with self.lock:
                    self._reap()
                continue
            try:
                self._run(job)
            except temporal.TemporalError as error:
                with self.lock:
                    job.state = 'cancelled' if error.code == 'CANCELLED' else 'failed'
                    job.error = _error(error.code)
                    job.pngs.clear()
            except Exception:
                with self.lock:
                    job.state, job.error = 'failed', _error('PROCESSING_FAILED')
                    job.pngs.clear()
            finally:
                self.pending.task_done()

    def _run(self, job):
        job.started = time.monotonic()
        self._check(job)
        with self.lock:
            job.state = 'sampling'
        samples = []
        for index in range(len(job.group.frames)):
            self._check(job)
            self._acquire_projection(job)
            try:
                data = temporal.load_frame(job.group, index, cancelled=job.cancel.is_set)
                samples.append(temporal.sample_values(data))
                del data
            finally:
                self.projection_lock.release()
            with self.lock:
                job.completed = index + 1
        scale = temporal.shared_scale(samples)
        del samples
        with self.lock:
            job.state = 'rendering'
        for index in range(len(job.group.frames)):
            self._check(job)
            self._acquire_projection(job)
            try:
                data = temporal.load_frame(job.group, index, cancelled=job.cancel.is_set)
                png, window = self.renderer(data, job.params, scale)
                del data
            finally:
                self.projection_lock.release()
            self._check(job)
            if not isinstance(png, bytes) or not png.startswith(b'\x89PNG\r\n\x1a\n'):
                raise temporal.TemporalError('PROCESSING_FAILED')
            with self.lock:
                self._check(job)
                used = sum(len(value) for current in self.jobs.values() for value in current.pngs.values())
                if used + len(png) > self.max_png_bytes:
                    raise temporal.TemporalError('RESOURCE_LIMIT')
                if job.window is not None and job.window != window:
                    raise temporal.TemporalError('INCONSISTENT_INTENSITY_WINDOW')
                job.pngs[index], job.window = png, window
                job.completed = len(job.group.frames) + index + 1
        with self.lock:
            self._check(job)
            job.state = 'ready'


def attach_temporal(app, resolver, *, projection_lock, renderer=None):
    """Mount on the already authenticated local host; resolver(ticket, origin)."""
    if hasattr(app, '_neuro_temporal_service'):
        return app._neuro_temporal_service
    from starlette.concurrency import run_in_threadpool
    service = TemporalService(resolver, projection_lock, renderer)

    def failed(error):
        code = error.code if isinstance(error, temporal.TemporalError) else 'PROCESSING_FAILED'
        status = 404 if code in ('UNKNOWN_JOB', 'UNKNOWN_GROUP') else 409 if code == 'NOT_READY' else 422
        return JSONResponse({'error': _error(code)}, status_code=status, headers={'Cache-Control': 'no-store'})

    async def body(request):
        raw = await request.body()
        if not 0 < len(raw) <= 32768:
            raise temporal.TemporalError('INVALID_REQUEST')
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError):
            raise temporal.TemporalError('INVALID_REQUEST') from None
        return value

    @app.post(PREFIX + '/discover')
    async def discover(request: Request):
        try:
            return await run_in_threadpool(service.discover, await body(request))
        except Exception as error:
            return failed(error)

    @app.post(PREFIX + '/prepare')
    async def prepare(request: Request):
        try:
            return service.prepare(await body(request))
        except Exception as error:
            return failed(error)

    @app.get(PREFIX + '/status/{job}')
    def status(job: str):
        try:
            return service.status(job)
        except Exception as error:
            return failed(error)

    @app.get(PREFIX + '/frame/{job}/{index}')
    def frame(job: str, index: int):
        try:
            return Response(service.frame(job, index), media_type='image/png', headers={'Cache-Control': 'no-store'})
        except Exception as error:
            return failed(error)

    @app.post(PREFIX + '/cancel/{job}')
    def cancel(job: str):
        try:
            return service.cancel(job)
        except Exception as error:
            return failed(error)

    app._neuro_temporal_service = service
    app.router.add_event_handler('shutdown', service.close)
    return service

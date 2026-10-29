"""Host-side study coordination. Scientific libraries only run in child processes."""
import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
import traceback
import uuid
from pathlib import Path

from . import __version__
from .adapters.base import RunCancelled
from .contracts import (validate_identifier, validate_study_request, validate_model_result,
                        validate_worker_progress)
from .model_registry import load_catalog, verify_artifacts
from .orchestrator import StudyRunContext, build_study_plan, run_study
from .series_selection import describe_series, suggest_bindings, evaluate_eligibility
from .study_types import SeriesDescriptor
from .integrity import sha256_file

TERMINAL = frozenset(('completed', 'empty', 'partial', 'failed', 'cancelled', 'interrupted'))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    for attempt in range(8):
        try:
            os.replace(temporary, path)
            break
        except PermissionError as error:
            if (os.name != 'nt' or getattr(error, 'winerror', None) not in (5, 32, 33)
                    or attempt == 7):
                raise
            # Short-lived readers/antivirus may deny a Windows rename while
            # the old state is open. Preserve atomic replacement and bound wait.
            time.sleep(min(.01 * 2 ** attempt, .25))


class StudyService:
    def __init__(self, settings, host_services, *, catalog=None):
        self.settings, self.host = settings, host_services
        self.catalog = catalog if catalog is not None else {m['id']: m for m in load_catalog()}
        self._lock = threading.RLock()
        self._jobs, self._requests = {}, {}
        self._closed = False
        from .result_store import ResultStore
        self.store = ResultStore(settings.data_dir, catalog=self.catalog)
        self._recover()

    def _recover(self):
        folder = self.settings.data_dir / 'jobs'
        if not folder.is_dir(): return
        for path in folder.glob('*/state.json'):
            try:
                state = json.loads(path.read_text(encoding='utf-8'))
                if state.get('schema') != 'neuro-rt/job-state/1': continue
                ident = validate_identifier(state['id'], 'study_id')
                if path.parent.name != ident: continue
                if state['status'] not in TERMINAL:
                    state.update(status='interrupted', message='Interrompido ao encerrar a estação. Reenvie para tentar novamente.')
                    atomic_json(path, state)
                attempt = state.get('attempt', 1)
                if type(attempt) is not int or attempt < 1: continue
                directory = path.parent if attempt == 1 else path.parent / 'attempts' / str(attempt)
                self._jobs[ident] = {**state, 'base_directory': path.parent, 'directory': directory,
                    'cancel': threading.Event(), 'process': None, 'thread': None, 'ticket': None}
            except (OSError, ValueError, KeyError, TypeError):
                continue
        for job in self._jobs.values():
            try:
                payload = json.loads((job['base_directory'] / 'request-intent.json').read_text(encoding='utf-8'))
                ids = [s['study_id'] for s in payload['studies']]
                if all(i in self._jobs for i in ids):
                    self._requests[payload['request_id']] = {'ids': ids,
                        'digest': hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()}
            except (OSError, ValueError, KeyError, TypeError): continue

    def _public(self, job):
        return {key: job[key] for key in ('id', 'status', 'message', 'model_ids',
                'reference', 'progress', 'result') if key in job}

    def _update(self, ident, **values):
        with self._lock:
            job = self._jobs[ident]
            job.update(values)
            atomic_json(job.get('base_directory', job['directory']) / 'state.json',
                {'schema': 'neuro-rt/job-state/1', 'attempt': job.get('attempt', 1), **self._public(job)})

    def job(self, ident, revision=None):
        with self._lock:
            if ident not in self._jobs: raise KeyError('Resultado não encontrado.')
            job = self._public(self._jobs[ident])
            if revision is not None:
                view = self.store.public_view(self.store.load_manifest(ident, revision)).to_dict()
                job.update(status=view['status'], result=view)
            return job

    def list_jobs(self):
        with self._lock:
            return [self._public(job) for job in self._jobs.values()]

    def capabilities(self):
        models = {mid: verify_artifacts(spec, self.settings.plugin_paths or self.settings.models_dir)
                  for mid, spec in self.catalog.items()}
        runtimes = {}
        for spec in self.catalog.values():
            ident = spec.get('runtime_id')
            python = self.settings.runtime_python(ident)
            runtimes[ident] = {'available': python is not None and Path(python).is_file(),
                              'reason': 'O ambiente deste modelo precisa ser preparado.'}
        if 'cranio_buti' in self.catalog:
            from integration.buti_host import capabilities as host_capabilities
            info = host_capabilities(self.settings.host_app, self.settings.host_python)['cranio_buti']
            models['cranio_buti'] = {'model_id': 'cranio_buti',
                'status': 'ready' if info['available'] else 'missing',
                'verified_files': [], 'missing_files': [], 'errors': [info['reason']] if info['reason'] else []}
            runtimes['host-nnunet'] = {'available': info['available'], 'reason': info['reason']}
        return {'models': models, 'runtimes': runtimes}

    def selection(self, tickets, category=None):
        if not isinstance(tickets, list) or len(tickets) > 120 or not all(isinstance(x, str) for x in tickets):
            raise ValueError('Lista de séries inválida.')
        descriptors = [describe_series(ticket, self.host) for ticket in dict.fromkeys(tickets)]
        capabilities = self.capabilities()
        capabilities['series'] = {d.ticket: d for d in descriptors}
        models = []
        for spec in self.catalog.values():
            if 'auxiliary' in spec['groups']: continue
            if category and category not in spec['groups'] and 'anatomia' not in spec['groups']: continue
            bindings = suggest_bindings(descriptors, spec)
            # suggest_bindings returns a binding list; it never invents a channel.
            eligibility = evaluate_eligibility(spec, bindings, capabilities)
            models.append({'id': spec['id'], 'label': spec['label'], 'groups': spec['groups'],
                'channels': spec['channels'], 'classes': spec['classes'],
                'reference_role': spec.get('reference_role'), 'revision': spec.get('revision'),
                'license': spec['license'], 'source_url': spec.get('source_url'),
                'help': spec.get('help', {}), 'bindings': [b.to_dict() for b in bindings],
                'eligibility': eligibility.to_dict()})
        return {'series': [{'ticket': d.ticket, 'modality': d.modality,
                    'group_key': hashlib.sha256((d.subject_key + '\0' + d.study_key).encode()).hexdigest(),
                    'sequence_candidates': d.sequence_candidates, 'source_format': d.source_format}
                    for d in descriptors], 'models': models}

    def check_capabilities(self, study):
        capabilities = self.capabilities()
        for mid in study.model_ids:
            decision = evaluate_eligibility(self.catalog[mid], study.bindings_by_model[mid], capabilities)
            if not decision.selectable:
                raise ValueError('Modelo indisponível: entradas ou ambiente necessários não estão preparados.')

    def submit(self, payload):
        if not isinstance(payload, dict) or payload.get('explicit_request') is not True:
            raise ValueError('A segmentação exige solicitação explícita.')
        request_id = validate_identifier(payload.get('request_id'), 'request_id')
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
        with self._lock:
            previous = self._requests.get(request_id)
            if previous:
                if previous['digest'] != digest: raise ValueError('O identificador já pertence a outro pedido.')
                return {'request_id': request_id, 'studies': [self.job(i) for i in previous['ids']]}
        # Resolve only server-issued tickets. Paths never come from this payload.
        tickets = set()
        items = payload.get('studies')
        if not isinstance(items, list) or not items or len(items) > 120:
            raise ValueError('Lista de estudos inválida.')
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get('bindings_by_model'), dict):
                raise ValueError('Associação de séries inválida.')
            tickets.add(item.get('reference'))
            for bindings in item.get('bindings_by_model', {}).values():
                if not isinstance(bindings, list) or not all(isinstance(b, dict) for b in bindings):
                    raise ValueError('Associação de séries inválida.')
                tickets.update(b.get('series_ticket') for b in bindings)
        if any(not isinstance(t, str) for t in tickets): raise ValueError('Ticket inválido.')
        sources = {t: self.host.resolve_series_ticket(t) for t in tickets}
        index = {t: describe_series(t, self.host) for t in tickets}
        request = validate_study_request(payload, self.catalog, index)
        for item in request.studies:
            build_study_plan(item, self.catalog)
            self.check_capabilities(item)
        with self._lock:
            if self._closed: raise RuntimeError('Serviço encerrado.')
            previous = self._requests.get(request.request_id)
            if previous:
                if previous['digest'] != digest: raise ValueError('O identificador já pertence a outro pedido.')
                return {'request_id': request.request_id,
                        'studies': [self.job(ident) for ident in previous['ids']]}
            if any(item.study_id in self._jobs for item in request.studies):
                raise ValueError('O estudo já existe; use uma nova execução ou a ação de retentativa.')
            ids = [item.study_id for item in request.studies]
            if any((self.settings.data_dir / 'jobs' / ident).exists() for ident in ids):
                raise ValueError('A pasta de uma execução já existe; use outro identificador.')
            accepted = threading.Event()
            def start_after_acceptance(item):
                accepted.wait()
                if self._jobs[item.study_id]['status'] != 'failed':
                    self._run(request, item, sources)
            for item in request.studies:
                directory = self.settings.data_dir / 'jobs' / item.study_id
                job = {'id': item.study_id, 'status': 'queued', 'message': 'Aguardando na fila da estação.',
                    'reference': item.reference, 'model_ids': item.model_ids, 'directory': directory,
                    'base_directory': directory, 'attempt': 1,
                    'ticket': None, 'cancel': threading.Event(), 'process': None, 'thread': None}
                self._jobs[item.study_id] = job
            self._requests[request.request_id] = {'digest': digest, 'ids': ids}
            try:
                # Persist every intent before touching the shared queue. Workers
                # wait behind one gate until the complete request is accepted.
                for item in request.studies:
                    job = self._jobs[item.study_id]; directory = job['directory']
                    directory.mkdir(parents=True, exist_ok=False)
                    atomic_json(directory / 'request.json', request.to_dict())
                    atomic_json(directory / 'request-intent.json', payload)
                    atomic_json(directory / 'source-bindings.json', sources)
                    self._update(item.study_id)
                for item in request.studies:
                    job = self._jobs[item.study_id]
                    job['ticket'] = self.host.queue_bridge.enqueue_study(request.request_id, item)
                for item in request.studies:
                    thread = threading.Thread(target=start_after_acceptance, args=(item,), daemon=True)
                    self._jobs[item.study_id]['thread'] = thread
                    thread.start()
            except Exception as error:
                for ident in ids:
                    job = self._jobs[ident]; job['cancel'].set()
                    job.update(status='failed', message='O pedido não foi aceito pela fila. Nenhum estudo foi iniciado.')
                    if job['ticket'] is not None:
                        try: self.host.queue_bridge.cancel(job['ticket'])
                        except Exception: pass
                    try:
                        directory = job['directory']; directory.mkdir(parents=True, exist_ok=True)
                        atomic_json(directory / 'request.json', request.to_dict())
                        atomic_json(directory / 'request-intent.json', payload)
                        atomic_json(directory / 'source-bindings.json', sources)
                        with (directory / 'errors.log').open('a', encoding='utf-8') as stream:
                            stream.write(''.join(traceback.format_exception(error)))
                        self._update(ident)
                    except OSError:
                        # A failing disk cannot acknowledge durable state; keep
                        # the failed in-memory receipt and never open the gate.
                        pass
                raise
            finally:
                accepted.set()
            return {'request_id': request.request_id, 'studies': [self.job(ident) for ident in ids]}

    def _execute(self, command, directory, log_name, event, ident, *, on_progress=None):
        if event.is_set(): raise RunCancelled()
        progress_path, last_sequence = directory / 'worker-progress.json', 0
        if on_progress is not None: progress_path.unlink(missing_ok=True)
        def read_progress():
            nonlocal last_sequence
            if on_progress is None: return
            try:
                if progress_path.stat().st_size > 512: return
                value = validate_worker_progress(json.loads(progress_path.read_text(encoding='utf-8')))
            except (OSError, ValueError, TypeError):
                return
            if value['seq'] > last_sequence:
                last_sequence = value['seq']
                on_progress(value['stage'], value['fraction'])
        env = dict(os.environ)
        env.update(OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2',
                   ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS='2', PYTHONUTF8='1',
                   PYTHONDONTWRITEBYTECODE='1')
        from .process_tree import ManagedProcess
        with (directory / log_name).open('wb') as log:
            with self._lock:
                if event.is_set() or self._closed: raise RunCancelled()
                process = ManagedProcess(command, cwd=self.settings.root, env=env, stdout=log)
                self._jobs[ident]['process'] = process
            try:
                while process.poll() is None:
                    read_progress()
                    if event.wait(.1):
                        process.terminate_tree()
                        raise RunCancelled()
                read_progress()
                if process.returncode: raise RuntimeError('O motor local falhou; consulte o registro privado.')
            finally:
                try:
                    process.close()
                except Exception:
                    with self._lock: self._jobs[ident]['release_safe'] = False
                    raise
                else:
                    with self._lock: self._jobs[ident]['process'] = None

    def prepare_inputs(self, item, sources, directory, event):
        private = {'reference': item.reference, 'sources': {t: sources[t] for t in
            {item.reference, *(b.series_ticket for bs in item.bindings_by_model.values() for b in bs)}},
            'host_app': str(self.settings.host_app)}
        atomic_json(directory / 'input-sources.json', private)
        self._execute([self.settings.host_python, '-m', 'neuro_rt.study_worker', '--task', 'prepare',
            '--job-dir', str(directory)], directory, 'prepare.log', event, item.study_id)
        prepared = json.loads((directory / 'prepared-inputs.json').read_text(encoding='utf-8'))
        return ({t: SeriesDescriptor(**d) for t, d in prepared['series_index'].items()},
                {t: Path(p) for t, p in prepared['authorized_inputs'].items()},
                {t: Path(p) for t, p in prepared['source_to_reference'].items()})

    def run_model(self, spec, context, event):
        context.job_dir.mkdir(parents=True, exist_ok=True)
        data = {'model_spec': spec, 'bindings': [b.to_dict() for b in context.bindings],
            'reference': context.reference.to_dict(),
            'series_index': {t: d.to_dict() for t, d in context.series_index.items()},
            'authorized_inputs': {t: str(p) for t, p in context.authorized_inputs.items()},
            'source_to_reference': {t: str(p) for t, p in context.source_to_reference.items()},
            'device': context.device, 'models_dir': str(context.models_dir),
            'host_app': str(self.settings.host_app), 'host_python': self.settings.host_python,
            'study_id': context.study_id,
            'allow_legacy_models': self.settings.plugin_paths is None}
        atomic_json(context.job_dir / 'model-context.json', data)
        python = self.settings.runtime_python(spec['runtime_id'])
        if not python: raise RuntimeError('Ambiente do modelo não preparado.')
        ident = context.study_id
        self._execute([python, '-m', 'neuro_rt.study_worker', '--task', 'model', '--job-dir',
            str(context.job_dir)], context.job_dir, 'model.log', event, ident, on_progress=context.progress)
        return validate_model_result(json.loads((context.job_dir / 'model-result.json').read_text(encoding='utf-8')), spec)

    def _run(self, request, item, sources):
        ident = item.study_id
        job = self._jobs[ident]
        directory, event, lease = job['directory'], job['cancel'], None
        outcome = 'failed'
        try:
            lease = self.host.queue_bridge.await_turn(job['ticket'], event)
            if event.is_set(): raise RunCancelled()
            preference = self.host.device_preference()
            if preference not in ('auto', 'cpu', 'cuda'):
                raise ValueError('Preferência de processamento inválida.')
            # Freeze the station preference when this item receives its turn.
            effective = 'cuda' if preference == 'cuda' else 'cpu'
            self._report_stage(ident, 'preparing', 'Conferindo séries e alinhamento.')
            if job.get('prepared_from') is not None:
                try:
                    index, inputs, transforms = self._reuse_preparation(job['prepared_from'], directory)
                except (OSError, ValueError, KeyError, TypeError):
                    index, inputs, transforms = self.prepare_inputs(item, sources, directory, event)
            else:
                index, inputs, transforms = self.prepare_inputs(item, sources, directory, event)
            atomic_json(directory / 'preparation-cache.json', {
                'series_index': {t: d.to_dict() for t, d in index.items()},
                'authorized_inputs': {t: str(p) for t, p in inputs.items()},
                'source_to_reference': {t: str(p) for t, p in transforms.items()},
                'input_hashes': {t: sha256_file(p) for t, p in inputs.items()},
                'transform_hashes': {t: sha256_file(p) for t, p in transforms.items()}})
            keys = self._execution_keys(item, index, inputs, transforms, effective)
            atomic_json(directory / 'execution-keys.json', keys)
            def event_callback(value):
                self._update(ident, status='running' if value['status'] in TERMINAL else value['status'], progress=value,
                             message='Processando os modelos selecionados.')
                self.host.queue_bridge.report(job['ticket'], value)
            def error_sink(model, error):
                with (directory / 'errors.log').open('a', encoding='utf-8') as stream:
                    stream.write(model + '\n' + ''.join(traceback.format_exception(error)))
            context = StudyRunContext(index[item.reference], index, inputs, directory,
                self.settings.models_dir, effective, preference, __version__, request.request_id,
                cancel_requested=event.is_set, on_event=event_callback,
                error_sink=error_sink, source_to_reference=transforms,
                execution_keys=keys, previous_results=job.get('previous_results', {}))
            result = run_study(build_study_plan(item, self.catalog), context,
                lambda spec, ctx: self.run_model(spec, ctx, event))
            atomic_json(directory / 'study-manifest.json', result.to_dict())
            if request.export_rtstruct and any(r.masks for r in result.results) and not event.is_set():
                self._report_stage(ident, 'exporting', 'Gravando os contornos pelo Local Suite.')
                try:
                    self._execute([self.settings.host_python, '-m', 'neuro_rt.export_study',
                        '--job-dir', str(directory), '--host-app', str(self.settings.host_app)],
                        directory, 'export.log', event, ident)
                except RunCancelled: raise
                except Exception as error:
                    error_sink('export', error)
                    data = json.loads((directory / 'study-manifest.json').read_text(encoding='utf-8'))
                    data['status'] = 'partial'
                    if data.get('export_status') not in ('failed', 'incomplete'):
                        data['export_status'] = 'failed'
                    atomic_json(directory / 'study-manifest.json', data)
            data = json.loads((directory / 'study-manifest.json').read_text(encoding='utf-8'))
            if not event.is_set():
                try:
                    self._report_stage(ident, 'visualizing', 'Preparando os visores e as estruturas.')
                    self.build_views(ident, directory, event)
                    data = json.loads((directory / 'study-manifest.json').read_text(encoding='utf-8'))
                except RunCancelled: raise
                except Exception as error:
                    error_sink('views', error)
                    if any(r['masks'] for r in data['results']): data['status'] = 'partial'
                    atomic_json(directory / 'study-manifest.json', data)
            if event.is_set():
                data['status'] = 'cancelled'
                if data.get('export_status') == 'pending': data['export_status'] = 'incomplete'
                atomic_json(directory / 'study-manifest.json', data)
            outcome = data['status']
            self.publish(ident, data)
            self._update(ident, message={
                'empty': 'O modelo não produziu contornos; isso não indica ausência de doença.',
                'partial': 'Resultado parcial disponível para revisão.',
                'cancelled': 'Processamento cancelado; resultados anteriores preservados.',
                'failed': 'Os modelos falharam. Consulte os registros locais.'
            }.get(outcome, 'Resultado disponível para revisão.'))
        except RunCancelled:
            outcome = 'cancelled'
            # An exporter may have persisted its terminal receipt immediately
            # before cancellation. Read that manifest without exporting again.
            manifest_path = directory / 'study-manifest.json'
            if manifest_path.is_file():
                try:
                    data = json.loads(manifest_path.read_text(encoding='utf-8'))
                    data['status'] = 'cancelled'
                    if data.get('export_status') == 'pending': data['export_status'] = 'incomplete'
                    atomic_json(manifest_path, data)
                    self.publish(ident, data)
                except Exception as error:
                    with (directory / 'errors.log').open('a', encoding='utf-8') as stream:
                        stream.write(''.join(traceback.format_exception(error)))
            self._update(ident, message='Processamento cancelado; resultados anteriores preservados.')
        except Exception as error:
            from integration.queue_bridge import QueueCancelled
            outcome = 'cancelled' if event.is_set() or isinstance(error, QueueCancelled) else 'failed'
            with (directory / 'errors.log').open('a', encoding='utf-8') as stream:
                stream.write(''.join(traceback.format_exception(error)))
            self._update(ident, message='Processamento cancelado.' if outcome == 'cancelled'
                else 'O processamento falhou. Consulte os registros locais.')
        finally:
            # _execute always terminates/reaps its child before this release.
            if lease is not None and job.get('release_safe', True): lease.finish(outcome)
            self._update(ident, status=outcome)

    def build_views(self, ident, directory, event):
        self._execute([self.settings.host_python, '-m', 'neuro_rt.build_study_views',
            '--job-dir', str(directory), '--host-app', str(self.settings.host_app)],
            directory, 'views.log', event, ident)

    def _report_stage(self, ident, stage, message):
        progress = {'status': stage, 'fraction': 0.}
        self._update(ident, status=stage, message=message, progress=progress)
        self.host.queue_bridge.report(self._jobs[ident]['ticket'], progress)

    def _execution_keys(self, item, index, inputs, transforms, device):
        inputs_hash = {t: sha256_file(p) for t, p in inputs.items()}
        transforms_hash = {t: sha256_file(p) for t, p in transforms.items()}
        keys = {}
        for mid in item.model_ids:
            tickets = {item.reference, *(b.series_ticket for b in item.bindings_by_model[mid])}
            identity = {'plugin_version': __version__, 'spec': self.catalog[mid], 'device': device,
                'reference': index[item.reference].to_dict(),
                'bindings': [b.to_dict() for b in item.bindings_by_model[mid]],
                'inputs': {t: inputs_hash.get(t) for t in sorted(tickets)},
                'transforms': {t: transforms_hash[t] for t in sorted(tickets) if t in transforms_hash}}
            keys[mid] = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        return keys

    def _reuse_preparation(self, old_directory, directory):
        old_directory, directory = Path(old_directory), Path(directory)
        cached = json.loads((old_directory / 'preparation-cache.json').read_text(encoding='utf-8'))
        inputs, transforms = {}, {}
        reference = json.loads((old_directory / 'request.json').read_text(encoding='utf-8'))
        reference = next(i['reference'] for i in reference['studies'] if i['study_id'] == directory.parents[1].name)
        (directory / 'inputs').mkdir(exist_ok=True)
        (directory / 'transforms').mkdir(exist_ok=True)
        for number, (ticket, file) in enumerate(cached['authorized_inputs'].items()):
            target = directory / 'inputs' / ('reference.nii.gz' if ticket == reference else f'series_{number}.nii.gz')
            shutil.copyfile(file, target); inputs[ticket] = target
            if sha256_file(target) != cached['input_hashes'][ticket]:
                raise ValueError('Entrada preparada alterada durante a cópia.')
        for number, (ticket, file) in enumerate(cached['source_to_reference'].items()):
            target = directory / 'transforms' / f'{number}.tfm'
            shutil.copyfile(file, target); transforms[ticket] = target
            if sha256_file(target) != cached['transform_hashes'][ticket]:
                raise ValueError('Transformação preparada alterada durante a cópia.')
        for name in ('source.json', 'input-sources.json'):
            if (old_directory / name).is_file(): shutil.copyfile(old_directory / name, directory / name)
        if (old_directory / 'dicom_source').is_dir():
            shutil.copytree(old_directory / 'dicom_source', directory / 'dicom_source', dirs_exist_ok=True)
        return ({t: SeriesDescriptor(**d) for t, d in cached['series_index'].items()}, inputs, transforms)

    def _preparation_complete(self, item, cached):
        tickets = {item.reference, *(b.series_ticket for bs in item.bindings_by_model.values() for b in bs)}
        try:
            return (tickets <= set(cached['series_index'])
                and tickets <= set(cached['authorized_inputs'])
                and tickets - {item.reference} <= set(cached['source_to_reference'])
                and all(sha256_file(p) == cached[hash_field][t]
                        for field, hash_field in (('authorized_inputs', 'input_hashes'),
                                                  ('source_to_reference', 'transform_hashes'))
                        for t, p in cached[field].items()))
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def retry(self, ident, *, explicit_request=False):
        if explicit_request is not True: raise ValueError('A repetição exige solicitação explícita.')
        with self._lock:
            job = self._jobs.get(ident)
            if job is None: raise KeyError('Resultado não encontrado.')
            if self._closed or job['status'] not in TERMINAL:
                raise RuntimeError('Aguarde o estudo encerrar antes de repetir.')
            old = job['directory']
            payload = json.loads((old / 'request.json').read_text(encoding='utf-8'))
            sources = json.loads((old / 'source-bindings.json').read_text(encoding='utf-8'))
            cached = old / 'preparation-cache.json'
            from types import SimpleNamespace
            index = ({t: SeriesDescriptor(**d) for t, d in
                      json.loads(cached.read_text(encoding='utf-8'))['series_index'].items()} if cached.is_file()
                     else {t: describe_series(t, SimpleNamespace(resolve_series_ticket=lambda _, v=v: v))
                           for t, v in sources.items()})
            payload.update(request_id=uuid.uuid4().hex)
            payload['studies'] = [s for s in payload['studies'] if s['study_id'] == ident]
            request = validate_study_request(payload, self.catalog, index)
            item = request.studies[0]
            self.check_capabilities(item)
            previous, old_keys = {}, {}
            try:
                saved = self.store.load_manifest(ident)
                old_keys = json.loads((old / 'execution-keys.json').read_text(encoding='utf-8'))
                previous = {r.model_id: {'execution_key': old_keys.get(r.model_id), 'result': r}
                            for r in saved.results if r.status in ('completed', 'empty')}
            except (OSError, ValueError): pass
            attempt = job.get('attempt', 1) + 1
            directory = job['base_directory'] / 'attempts' / str(attempt)
            directory.mkdir(parents=True, exist_ok=False)
            # Copy verified immutable masks into this execution's private tree.
            # Builders/exporters keep their strict job containment boundary.
            from dataclasses import replace
            for mid, cached_result in list(previous.items()):
                restored = []
                try:
                    for number, mask in enumerate(cached_result['result'].masks):
                        record = next(a for a in saved.artifacts if a['path'] == mask.path and a['kind'] == 'mask')
                        artifact = self.store.resolve_artifact(ident, record['artifact_id'])
                        target = directory / 'masks' / mid / f'class_{number}.nii.gz'
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(artifact.path, target)
                        if sha256_file(target) != record['sha256']:
                            raise ValueError('Máscara anterior alterada durante a cópia.')
                        restored.append(replace(mask, path=str(target)))
                    previous[mid]['result'] = replace(cached_result['result'], masks=restored)
                except (OSError, ValueError, StopIteration):
                    previous.pop(mid)
            atomic_json(directory / 'request.json', request.to_dict())
            atomic_json(directory / 'source-bindings.json', sources)
            ticket = self.host.queue_bridge.enqueue_study(request.request_id, item)
            reusable = (cached.is_file() and self._preparation_complete(item,
                json.loads(cached.read_text(encoding='utf-8'))))
            job.update(directory=directory, attempt=attempt, cancel=threading.Event(), ticket=ticket,
                process=None, previous_results=previous, prepared_from=old if reusable else None)
            self._update(ident, status='queued', message='Repetição aguardando na fila da estação.')
            thread = threading.Thread(target=self._run, args=(request, item, sources), daemon=True)
            job['thread'] = thread; thread.start()
            return self._public(job)

    def publish(self, ident, manifest):
        from .result_store import public_view
        self.store.register_job(ident, self._jobs[ident]['directory'])
        revision = self.store.save_manifest(manifest)
        saved = self.store.load_manifest(ident, revision)
        view = public_view(saved, catalog=self.catalog).to_dict()
        self._update(ident, result=view)
        self.host.register_result({'study_id': ident, 'manifest': manifest,
                                   'job_dir': str(self._jobs[ident]['directory'])})

    def cancel(self, ident):
        with self._lock:
            job = self._jobs.get(ident)
            if job is None: raise KeyError('Resultado não encontrado.')
            if job['status'] in TERMINAL: return self._public(job)
            job['cancel'].set()
            if job['ticket'] is not None: self.host.queue_bridge.cancel(job['ticket'])
            return self._public(job)

    def close(self):
        with self._lock:
            self._closed = True
            jobs = list(self._jobs.values())
            for job in jobs: job['cancel'].set()
        for job in jobs:
            thread = job.get('thread')
            if thread and thread is not threading.current_thread(): thread.join(timeout=8)

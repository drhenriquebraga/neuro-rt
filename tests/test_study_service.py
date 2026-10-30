import tempfile
import threading
import time
import unittest
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

from neuro_rt.service import Settings
from neuro_rt.study_types import ModelResult, SeriesDescriptor
from test_pipeline import TEMP_ROOT


class Lease:
    def __init__(self, bridge): self.bridge = bridge
    def finish(self, outcome): self.bridge.finished.append(outcome)


class Bridge:
    def __init__(self): self.finished = []; self.claims = []
    def enqueue_study(self, request, study):
        return SimpleNamespace(id=study.study_id, request_id=request)
    def await_turn(self, ticket, event):
        self.claims.append(ticket.id)
        return Lease(self)
    def report(self, *args): pass
    def cancel(self, ticket): pass


class StudyServiceTests(unittest.TestCase):
    def test_atomic_state_write_retries_transient_windows_denial(self):
        from unittest.mock import patch
        from neuro_rt.study_service import atomic_json
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            target = Path(tmp) / 'state.json'
            target.write_text('{"status":"old"}', encoding='utf-8')
            replace = os.replace
            denied = PermissionError('synthetic sharing denial'); denied.winerror = 5
            attempts = []
            def temporarily_denied(source, destination):
                if not attempts: attempts.append(True); raise denied
                return replace(source, destination)
            with patch('neuro_rt.study_service.os.replace', side_effect=temporarily_denied):
                atomic_json(target, {'status': 'new'})
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')), {'status': 'new'})

    def test_atomic_state_write_preserves_old_state_when_denial_is_permanent(self):
        from unittest.mock import patch
        from neuro_rt.study_service import atomic_json
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            target = Path(tmp) / 'state.json'
            target.write_text('{"status":"old"}', encoding='utf-8')
            denied = PermissionError('synthetic permanent denial'); denied.winerror = 5
            with patch('neuro_rt.study_service.os.replace', side_effect=denied):
                with self.assertRaises(PermissionError): atomic_json(target, {'status': 'new'})
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')), {'status': 'old'})

    def make(self, folder):
        from neuro_rt.study_service import StudyService
        bridge = Bridge()
        descriptor = SeriesDescriptor('ticket', '1.2', 'subject', 'study', 'MR')
        host = SimpleNamespace(queue_bridge=bridge, device_preference=lambda: 'cpu',
            resolve_series_ticket=lambda ticket: {**descriptor.to_dict(),
                'source': {'input_path': str(folder), 'series_uid': '1.2'}},
            register_result=lambda result: None)
        settings = Settings(folder)
        (folder / 'input.nii.gz').write_bytes(b'synthetic cached input')
        spec = {'id': 'model', 'catalog_state': 'verified', 'channels': [{'role': 'T1'}],
                'classes': [{'class_id': 'tumor'}], 'runtime_id': 'test'}
        service = StudyService(settings, host, catalog={'model': spec})
        service.check_capabilities = lambda study: None
        service.prepare_inputs = lambda item, sources, directory, event: (
            {'ticket': descriptor}, {'ticket': folder / 'input.nii.gz'}, {})
        service.run_model = lambda spec, context, event: ModelResult('model', 'empty')
        service.build_views = lambda *args: None
        return service, bridge

    def payload(self, request='request', study='study'):
        return {'schema': 'neuro-rt/request/2', 'explicit_request': True,
            'request_id': request, 'studies': [{'study_id': study,
                'reference': 'ticket', 'model_ids': ['model'], 'bindings_by_model': {
                'model': [{'role': 'T1', 'series_ticket': 'ticket'}]}}]}

    def finished(self, service, ident):
        for _ in range(100):
            job = service.job(ident)
            if job['status'] in ('completed', 'empty', 'partial', 'failed', 'cancelled'):
                return job
            time.sleep(.01)
        self.fail('O job não terminou')

    def test_explicit_request_and_authorized_tickets_required(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, bridge = self.make(Path(tmp))
            data = self.payload(); data['explicit_request'] = False
            with self.assertRaises(ValueError): service.submit(data)
            self.assertEqual(bridge.claims, [])
            service.close()

    def test_idempotency_and_empty_terminal_state_use_shared_queue(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, bridge = self.make(Path(tmp))
            job = service.submit(self.payload())['studies'][0]
            result = self.finished(service, job['id'])
            self.assertEqual(result['status'], 'empty')
            self.assertEqual(bridge.claims, ['study'])
            self.assertEqual(bridge.finished, ['empty'])
            repeated = service.submit(self.payload())
            self.assertEqual(repeated['studies'][0]['id'], job['id'])
            self.assertEqual(len(bridge.claims), 1)
            service.close()

    def test_failure_is_private_and_does_not_publish_success(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, bridge = self.make(Path(tmp))
            def fail(*args): raise RuntimeError('private patient path')
            service.run_model = fail
            job = service.submit(self.payload())['studies'][0]
            result = self.finished(service, job['id'])
            self.assertEqual(result['status'], 'failed')
            self.assertNotIn('private patient path', str(result))
            self.assertEqual(bridge.finished, ['failed'])
            service.close()

    def test_cancel_holds_lease_until_worker_returns(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, bridge = self.make(Path(tmp))
            started, release = threading.Event(), threading.Event()
            def running(spec, context, event):
                started.set(); release.wait(2)
                return ModelResult('model', 'cancelled')
            service.run_model = running
            job = service.submit(self.payload())['studies'][0]
            self.assertTrue(started.wait(1))
            service.cancel(job['id'])
            self.assertEqual(bridge.finished, [])
            release.set()
            result = self.finished(service, job['id'])
            self.assertEqual(result['status'], 'cancelled')
            self.assertEqual(bridge.finished, ['cancelled'])
            service.close()

    def test_retry_preserves_completed_models_and_creates_complete_revision(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, bridge = self.make(Path(tmp))
            import copy
            second = copy.deepcopy(service.catalog['model']); second['id'] = 'second'
            service.catalog['second'] = second
            calls = []
            def runner(spec, context, event):
                calls.append(spec['id'])
                if spec['id'] == 'second' and calls.count('second') == 1:
                    raise RuntimeError('first attempt fails')
                return ModelResult(spec['id'], 'empty')
            service.run_model = runner
            payload = self.payload()
            item = payload['studies'][0]
            item['model_ids'].append('second')
            item['bindings_by_model']['second'] = item['bindings_by_model']['model']
            first = service.submit(payload)['studies'][0]
            self.assertEqual(self.finished(service, first['id'])['status'], 'partial')
            service.retry(first['id'], explicit_request=True)
            retried = self.finished(service, first['id'])
            self.assertEqual(retried['status'], 'empty')
            self.assertEqual(calls, ['model', 'second', 'second'])
            self.assertEqual(retried['result']['revision'], 2)
            self.assertEqual(len(retried['result']['models']), 2)
            service.close()

    def test_restart_reopens_result_without_repeating_inference(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, _ = self.make(Path(tmp))
            first = service.submit(self.payload())['studies'][0]
            self.finished(service, first['id'])
            service.close()
            recovered, bridge = self.make(Path(tmp))
            same = recovered.submit(self.payload())['studies'][0]
            self.assertEqual(same['id'], first['id'])
            self.assertEqual(same['status'], 'empty')
            self.assertEqual(bridge.claims, [])
            self.assertEqual(same['result']['revision'], 1)
            recovered.close()

    def test_second_enqueue_failure_never_starts_first_study_and_is_recoverable(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, bridge = self.make(Path(tmp))
            original = service.host.resolve_series_ticket
            def resolve(ticket):
                record = original(ticket)
                record.update(ticket=ticket, series_uid='1.3' if ticket == 'other' else '1.2')
                return record
            service.host.resolve_series_ticket = resolve
            payload = self.payload()
            second = copy.deepcopy(payload['studies'][0])
            second.update(study_id='second', reference='other')
            second['bindings_by_model']['model'][0]['series_ticket'] = 'other'
            payload['studies'].append(second)
            cancelled, executions = [], []
            bridge.cancel = lambda ticket: cancelled.append(ticket.id)
            def enqueue(request, study):
                if study.study_id == 'second': raise RuntimeError('private enqueue failure')
                return SimpleNamespace(id=study.study_id, request_id=request)
            bridge.enqueue_study = enqueue
            service._run = lambda *args: executions.append(args[1].study_id)
            with self.assertRaises(RuntimeError): service.submit(payload)
            service.close()
            self.assertEqual(executions, [])
            self.assertEqual(cancelled, ['study'])
            self.assertEqual([j['status'] for j in service.list_jobs()], ['failed', 'failed'])
            recovered, recovered_bridge = self.make(Path(tmp))
            recovered.host.resolve_series_ticket = resolve
            repeated = recovered.submit(payload)
            self.assertEqual([j['status'] for j in repeated['studies']], ['failed', 'failed'])
            self.assertEqual(recovered_bridge.claims, [])
            recovered.close()

    def test_changed_preparation_cache_is_not_reused(self):
        for change in ('tamper', 'remove'):
            with self.subTest(change=change), tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
                service, _ = self.make(Path(tmp))
                original = service.prepare_inputs
                preparations = []
                def prepare(*args):
                    preparations.append(args[2])
                    source = Path(tmp) / 'input.nii.gz'
                    if not source.exists(): source.write_bytes(b'new synthetic input')
                    return original(*args)
                service.prepare_inputs = prepare
                service.submit(self.payload())
                self.assertEqual(self.finished(service, 'study')['status'], 'empty')
                source = Path(tmp) / 'input.nii.gz'
                if change == 'tamper': source.write_bytes(b'changed synthetic input')
                else: source.unlink()
                service.retry('study', explicit_request=True)
                self.assertEqual(self.finished(service, 'study')['status'], 'empty')
                self.assertEqual(len(preparations), 2)
                service.close()

    def test_cancel_during_views_keeps_export_receipt_and_visible_masks_after_restart(self):
        from neuro_rt.adapters.base import RunCancelled
        from neuro_rt.study_types import MaskArtifact, ExportReceipt
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, bridge = self.make(Path(tmp))
            exports = []
            def model(spec, context, event):
                context.job_dir.mkdir(parents=True, exist_ok=True)
                path = context.job_dir / 'mask.nii.gz'; path.write_bytes(b'synthetic immutable mask')
                return ModelResult('model', 'completed', [MaskArtifact('model', 'tumor', str(path))])
            service.run_model = model
            def export(command, directory, log_name, event, ident):
                exports.append(log_name)
                manifest = json.loads((directory / 'study-manifest.json').read_text(encoding='utf-8'))
                manifest['export_status'] = 'completed'
                manifest['export_receipt'] = ExportReceipt(str(directory / 'RS.dcm'), '1.2.999',
                    'ticket', ['model/tumor'], [], 1).to_dict()
                from neuro_rt.study_service import atomic_json
                atomic_json(directory / 'study-manifest.json', manifest)
            service._execute = export
            def cancel(ident, directory, event): event.set(); raise RunCancelled()
            service.build_views = cancel
            payload = self.payload(); payload['export_rtstruct'] = True
            service.submit(payload)
            job = self.finished(service, 'study')
            self.assertEqual(job['status'], 'cancelled')
            self.assertEqual(job['result']['status'], 'cancelled')
            masks = [a for a in job['result']['artifacts'] if a['kind'] == 'mask']
            self.assertEqual(len(masks), 1)
            saved = service.store.load_manifest('study')
            self.assertEqual(saved.export_status, 'completed')
            self.assertEqual(saved.export_receipt.sop_instance_uid, '1.2.999')
            self.assertEqual(exports, ['export.log'])
            service.close()
            recovered, recovered_bridge = self.make(Path(tmp))
            self.assertEqual(recovered.job('study')['result']['status'], 'cancelled')
            artifact = recovered.store.resolve_artifact('study', masks[0]['artifact_id'])
            self.assertEqual(artifact.path.read_bytes(), b'synthetic immutable mask')
            self.assertEqual(recovered_bridge.claims, [])
            recovered.close()

    def test_cancel_after_masks_publishes_cancelled_manifest(self):
        from neuro_rt.adapters.base import RunCancelled
        from neuro_rt.study_types import MaskArtifact
        for stage in ('export', 'views'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
                service, bridge = self.make(Path(tmp))
                published, exports = [], []
                service.run_model = lambda spec, context, event: ModelResult('model', 'completed',
                    [MaskArtifact('model', 'tumor', str(Path(tmp) / 'mask.nii.gz'))])
                service.publish = lambda ident, data: published.append(data)
                def export(command, directory, log_name, event, ident):
                    exports.append(log_name)
                    if stage == 'export': event.set(); raise RunCancelled()
                service._execute = export
                def views(ident, directory, event):
                    if stage == 'views': event.set(); raise RunCancelled()
                service.build_views = views
                payload = self.payload(); payload['export_rtstruct'] = True
                service.submit(payload)
                job = self.finished(service, 'study')
                self.assertEqual(job['status'], 'cancelled')
                self.assertEqual(len(published), 1)
                self.assertEqual(published[0]['status'], 'cancelled')
                self.assertEqual(published[0]['results'][0]['status'], 'completed')
                self.assertEqual(len(published[0]['results'][0]['masks']), 1)
                self.assertEqual(exports, ['export.log'])
                self.assertEqual(bridge.finished, ['cancelled'])
                service.close()

    def test_incomplete_preparation_is_retried_instead_of_reused(self):
        from dataclasses import replace
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, _ = self.make(Path(tmp))
            descriptor = service.prepare_inputs(None, None, None, None)[0]['ticket']
            other = replace(descriptor, ticket='other', series_uid='1.3')
            payload = self.payload()
            second = copy.deepcopy(service.catalog['model']); second['id'] = 'second'
            service.catalog['second'] = second
            payload['studies'][0]['model_ids'].append('second')
            payload['studies'][0]['bindings_by_model']['second'] = [{'role': 'T1', 'series_ticket': 'other'}]
            service.host.resolve_series_ticket = lambda ticket: {
                **(other if ticket == 'other' else descriptor).to_dict(), 'source': {}}
            preparations, calls = [], []
            def prepare(item, sources, directory, event):
                preparations.append(directory)
                inputs = {'ticket': Path(tmp) / 'input.nii.gz'}
                if len(preparations) > 1: inputs['other'] = Path(tmp) / 'input.nii.gz'
                return {'ticket': descriptor, 'other': other}, inputs, ({'other': Path(tmp) / 'input.nii.gz'} if len(preparations) > 1 else {})
            def run(spec, context, event):
                calls.append(spec['id'])
                if spec['id'] == 'second' and 'other' not in context.authorized_inputs: raise ValueError('unavailable channel')
                return ModelResult(spec['id'], 'empty')
            service.prepare_inputs, service.run_model = prepare, run
            service.submit(payload)
            self.assertEqual(self.finished(service, 'study')['status'], 'partial')
            service.retry('study', explicit_request=True)
            self.assertEqual(self.finished(service, 'study')['status'], 'empty')
            self.assertEqual(len(preparations), 2)
            self.assertEqual(calls, ['model', 'second', 'second'])
            service.close()

    def test_cancel_before_acceptance_gate_opens_becomes_terminal(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, bridge = self.make(Path(tmp))
            def enqueue(request, study):
                service.cancel(study.study_id)
                return SimpleNamespace(id=study.study_id, request_id=request)
            bridge.enqueue_study = enqueue
            service.submit(self.payload())
            self.assertEqual(self.finished(service, 'study')['status'], 'cancelled')
            service.close()

    def test_unconfirmed_process_tree_keeps_queue_lease(self):
        from unittest.mock import patch
        class UnsafeProcess:
            returncode = 0
            def __init__(self, *args, **kwargs): pass
            def poll(self): return 0
            def close(self): raise RuntimeError('tree exit unconfirmed')
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, bridge = self.make(Path(tmp))
            def run(spec, context, event):
                context.job_dir.mkdir(parents=True, exist_ok=True)
                service._execute(['synthetic'], context.job_dir, 'synthetic.log', event, context.study_id)
            service.run_model = run
            with patch('neuro_rt.process_tree.ManagedProcess', UnsafeProcess):
                service.submit(self.payload())
                self.assertEqual(self.finished(service, 'study')['status'], 'failed')
            self.assertFalse(service._jobs['study']['release_safe'])
            self.assertEqual(bridge.finished, [])
            service.close()

    def test_selection_groups_are_stable_and_do_not_expose_subject_or_study(self):
        from dataclasses import replace
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, _ = self.make(Path(tmp))
            service.catalog = {}
            service.capabilities = lambda: {'models': {}, 'runtimes': {}}
            reference = SeriesDescriptor('a', '1.2', 'private_subject', 'private_visit', 'MR')
            descriptors = {'a': reference, 'b': replace(reference, ticket='b', series_uid='1.3'),
                           'c': replace(reference, ticket='c', study_key='other_visit')}
            service.host.resolve_series_ticket = lambda ticket: descriptors[ticket]
            first = service.selection(['a', 'b', 'c'])
            second = service.selection(['a'])
            self.assertEqual(first['series'][0]['group_key'], first['series'][1]['group_key'])
            self.assertNotEqual(first['series'][0]['group_key'], first['series'][2]['group_key'])
            self.assertEqual(first['series'][0]['group_key'], second['series'][0]['group_key'])
            self.assertRegex(first['series'][0]['group_key'], '^[a-f0-9]{64}$')
            self.assertNotIn('private_subject', str(first))
            self.assertNotIn('private_visit', str(first))
            service.close()

    def test_job_directory_failure_does_not_leave_accepted_queue_or_restart(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, bridge = self.make(Path(tmp))
            original_resolve = service.host.resolve_series_ticket
            def resolve(ticket):
                record = original_resolve(ticket)
                record.update(ticket=ticket, series_uid='1.3' if ticket == 'other' else '1.2')
                return record
            service.host.resolve_series_ticket = resolve
            payload = self.payload()
            second = copy.deepcopy(payload['studies'][0]); second.update(study_id='second', reference='other')
            second['bindings_by_model']['model'][0]['series_ticket'] = 'other'
            payload['studies'].append(second)
            failed, enqueued = [], []
            original_mkdir = Path.mkdir
            def mkdir(path, *args, **kwargs):
                if path.name == 'second' and not failed:
                    failed.append(True); raise OSError('synthetic directory failure')
                return original_mkdir(path, *args, **kwargs)
            bridge.enqueue_study = lambda *args: enqueued.append(args)
            with patch.object(Path, 'mkdir', mkdir):
                with self.assertRaises(OSError): service.submit(payload)
            self.assertEqual(enqueued, [])
            self.assertEqual([j['status'] for j in service.list_jobs()], ['failed', 'failed'])
            service.close()
            recovered, recovered_bridge = self.make(Path(tmp))
            repeated = recovered.submit(payload)
            self.assertEqual([j['status'] for j in repeated['studies']], ['failed', 'failed'])
            self.assertEqual(recovered_bridge.claims, [])
            recovered.close()

    def test_invalid_request_or_study_ids_are_rejected_before_enqueue(self):
        for field in ('request_id', 'study_id'):
            for value in ('request 1', 'pedido/1', '_request', 'acentuádo', 'a' * 129,
                          'study.', 'study..', 'study ', 'CON', 'con.txt', 'PrN.other',
                          'AUX', 'NUL', 'COM1', 'lpt9.txt'):
                with self.subTest(field=field, value=value), tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
                    service, bridge = self.make(Path(tmp))
                    enqueued = []
                    bridge.enqueue_study = lambda *args: enqueued.append(args)
                    service._run = lambda *args: None
                    payload = self.payload()
                    (payload if field == 'request_id' else payload['studies'][0])[field] = value
                    with self.assertRaises(ValueError): service.submit(payload)
                    self.assertEqual(enqueued, [])
                    self.assertFalse((service.settings.data_dir / 'jobs').exists())
                    service.close()

    def test_accepted_ids_match_manifest_and_recovery_contract(self):
        from neuro_rt.result_store import validate_manifest
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, _ = self.make(Path(tmp))
            payload = self.payload(request='request.1', study='study.1')
            service.submit(payload)
            job = self.finished(service, 'study.1')
            self.assertEqual(job['status'], 'empty')
            saved = service.store.load_manifest('study.1')
            self.assertEqual(validate_manifest(saved, service.catalog).request_id, 'request.1')
            service.close()
            recovered, bridge = self.make(Path(tmp))
            self.assertEqual(recovered.submit(payload)['studies'][0]['status'], 'empty')
            self.assertEqual(bridge.claims, [])
            recovered.close()

    def test_device_preference_is_frozen_before_preparation(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service, _ = self.make(Path(tmp))
            current, reads, devices = ['cpu'], [], []
            entered, release = threading.Event(), threading.Event()
            original = service.prepare_inputs
            def preference(): reads.append(current[0]); return current[0]
            def prepare(*args):
                entered.set(); release.wait(5)
                return original(*args)
            def run(spec, context, event):
                devices.append(context.device)
                return ModelResult('model', 'empty')
            service.host.device_preference, service.prepare_inputs, service.run_model = preference, prepare, run
            try:
                service.submit(self.payload())
                self.assertTrue(entered.wait(3))
                self.assertEqual(reads, ['cpu'])
                current[0] = 'cuda'; release.set()
                self.assertEqual(self.finished(service, 'study')['status'], 'empty')
                self.assertEqual(devices, ['cpu'])
                self.assertEqual(service.store.load_manifest('study').device_preference, 'cpu')
            finally:
                release.set(); service.close()

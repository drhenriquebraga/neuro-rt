"""Controlled subprocess checkpoints; no model weights or scientific inference."""
import json
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch

import test_shared_queue as queue_helpers
import test_study_service as service_helpers
from neuro_rt.study_service import atomic_json

ROOT = Path(__file__).resolve().parents[1]

CONTROLLED_WORKER = r'''
from pathlib import Path
import sys, time
from neuro_rt.adapter_registry import ADAPTER_FACTORIES
from neuro_rt.study_types import ModelResult, MaskArtifact
from neuro_rt.study_worker import model
root = Path(sys.argv[1])
def wait(name):
    deadline = time.monotonic() + 30
    while not (root / name).exists():
        if time.monotonic() > deadline: raise RuntimeError('controlled worker timeout')
        time.sleep(.02)
class Controlled:
    def prepare(self, context): return context
    def predict(self, prepared, context):
        context.checkpoint('running', .25)
        wait('release-running')
        context.checkpoint('restoring', .75)
        wait('release-restoring')
    def normalize_result(self, raw, context):
        path = root / 'mask.nii.gz'; path.write_bytes(b'synthetic mask')
        return ModelResult('model', 'completed', [MaskArtifact('model', 'tumor', str(path))])
ADAPTER_FACTORIES['controlled'] = Controlled
model(root)
'''


class WorkerProgressTests(unittest.TestCase):
    setUp = queue_helpers.SharedQueueTests.setUp
    tearDown = queue_helpers.SharedQueueTests.tearDown

    def wait_for(self, predicate, description):
        deadline = time.monotonic() + 10
        while not predicate():
            if time.monotonic() > deadline: self.fail(description)
            time.sleep(.02)

    def test_progress_reader_rejects_untrusted_and_stale_events(self):
        service, _ = service_helpers.StudyServiceTests().make(Path(self.tmp.name))
        folder = Path(self.tmp.name) / 'progress-probe'; folder.mkdir()
        service._jobs['probe'] = {'process': None, 'cancel': threading.Event()}
        received = []
        events = iter([
            {'seq': 1, 'stage': 'running', 'fraction': .1},
            {'seq': 1, 'stage': 'restoring', 'fraction': .2},
            {'seq': 2, 'stage': 'running', 'fraction': .3, 'path': 'PRIVATE_SYNTHETIC'},
            {'seq': 2, 'stage': 'running', 'fraction': float('nan')},
            {'seq': 2, 'stage': 'running', 'fraction': True},
            {'seq': 2, 'stage': 'unknown', 'fraction': .3},
            {'seq': 0, 'stage': 'running', 'fraction': .3},
            {'seq': 3, 'stage': 'restoring', 'fraction': .8},
        ])
        class ControlledProcess:
            returncode = 0
            def __init__(self, *args, **kwargs): pass
            def poll(self):
                event = next(events, None)
                if event is None: return 0
                (folder / 'worker-progress.json').write_text(json.dumps(event), encoding='utf-8')
                return None
            def close(self): pass
        try:
            with patch('neuro_rt.process_tree.ManagedProcess', ControlledProcess):
                service._execute(['synthetic'], folder, 'probe.log', threading.Event(), 'probe',
                                 on_progress=lambda stage, fraction: received.append((stage, fraction)))
            self.assertEqual(received, [('running', .1), ('restoring', .8)])
        finally: service.close()

    def test_worker_checkpoints_reach_service_and_real_queue_before_release(self):
        service, _ = service_helpers.StudyServiceTests().make(Path(self.tmp.name))
        service.settings.root = ROOT
        service.settings.runtime_python = lambda _: sys.executable
        service.host.queue_bridge = self.bridge
        service.catalog['model']['adapter_id'] = 'controlled'
        service.run_model = type(service).run_model.__get__(service)
        execute = service._execute
        export_entered, export_release, views_entered, views_release = [threading.Event() for _ in range(4)]
        def controlled_execute(command, directory, log_name, event, ident, **kwargs):
            if log_name == 'model.log':
                command = [sys.executable, '-c', CONTROLLED_WORKER, str(directory)]
            if log_name == 'export.log':
                export_entered.set(); export_release.wait(10)
                data = json.loads((directory / 'study-manifest.json').read_text(encoding='utf-8'))
                data.update(status='partial', export_status='incomplete')
                atomic_json(directory / 'study-manifest.json', data)
                return
            return execute(command, directory, log_name, event, ident, **kwargs)
        service._execute = controlled_execute
        def views(*args): views_entered.set(); views_release.wait(10)
        service.build_views = views
        payload = service_helpers.StudyServiceTests().payload(); payload['export_rtstruct'] = True
        model_dir = service.settings.data_dir / 'jobs/study/models/model'
        try:
            service.submit(payload)
            ticket = service._jobs['study']['ticket']
            for stage, fraction in (('running', .25), ('restoring', .75)):
                self.wait_for(lambda: service.job('study').get('progress', {}).get('status') == stage,
                              f'checkpoint {stage} did not reach StudyService')
                self.assertEqual(service.job('study')['status'], stage)
                self.assertEqual(service.job('study')['progress']['fraction'], fraction)
                self.wait_for(lambda: self.host.cartao(ticket.id).get('neuro_progress', {}).get('stage') == stage,
                              f'checkpoint {stage} did not reach host queue')
                card = self.host.cartao(ticket.id)
                self.assertEqual(card['neuro_progress'], {'stage': stage, 'fraction': fraction})
                self.assertEqual(card['estado'], 'rodando')
                self.assertFalse(self.host.tentar_a_vez('lote'))
                (model_dir / f'release-{stage}').touch()
            self.assertTrue(export_entered.wait(10))
            self.assertEqual(self.host.cartao(ticket.id)['neuro_progress']['stage'], 'exporting')
            self.assertEqual(service.job('study')['status'], 'exporting')
            self.assertFalse(self.host.tentar_a_vez('lote'))
            export_release.set()
            self.assertTrue(views_entered.wait(10))
            self.assertEqual(self.host.cartao(ticket.id)['neuro_progress']['stage'], 'visualizing')
            self.assertEqual(service.job('study')['status'], 'visualizing')
            self.assertFalse(self.host.tentar_a_vez('lote'))
            views_release.set()
            self.wait_for(lambda: service.job('study')['status'] == 'partial', 'study did not finish')
            self.assertEqual(self.host.cartao(ticket.id)['estado'], 'parcial')
            self.assertIsNone(self.host._VEZ['dono'])
        finally:
            model_dir.mkdir(parents=True, exist_ok=True)
            for stage in ('running', 'restoring'): (model_dir / f'release-{stage}').touch()
            export_release.set(); views_release.set(); service.close()

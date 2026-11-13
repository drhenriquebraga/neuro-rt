"""ASGI API tests: synthetic arrays, host queue, no network or inference."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
import struct

import SimpleITK as sitk
import numpy as np
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'RECON_3D/app'))
import radai_projection as N
from integration.nidus_consensus import attach_consensus_api


class Queue:
    def __init__(self): self.events = []; self.is_cancelled = False
    def enqueue_study(self, request, study): self.events.append('enqueue'); return request
    def await_turn(self, ticket): return self
    def __enter__(self): self.events.append('lease'); return self
    def __exit__(self, *args): self.events.append('finish')
    def cancelled(self, ticket): return self.is_cancelled
    def report(self, ticket, progress): pass


class NidusConsensusAPITests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / 'runtime/test-tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = FastAPI()
        self.queue = Queue()
        self.app.state.neuro_rt = SimpleNamespace(token='synthetic-token',
            settings=SimpleNamespace(data_dir=self.root, host_app=self.root),
            host_services=SimpleNamespace(queue_bridge=self.queue))
        img = sitk.Image([15, 13, 9], sitk.sitkInt16)
        core = N.consenso(img, [{'lao': 0, 'cra': 0, 'pontos': [(15,15),(45,15),(45,45),(15,45)]}], lado=64)
        self.sessions = {'synthetic-session': {'b': 'synthetic-ticket', 'consenso': core}}
        attach_consensus_api(self.app, self.sessions, lambda b: (self.root, 'synthetic-uid'))

    def request(self, path, data, token='synthetic-token', origin='http://127.0.0.1'):
        async def invoke():
            raw = json.dumps(data).encode()
            headers = [(b'host',b'127.0.0.1'),(b'content-type',b'application/json'),
                       (b'origin',origin.encode()),(b'x-neuro-token',token.encode())]
            scope = {'type':'http','http_version':'1.1','method':'POST','scheme':'http',
                'path':path,'raw_path':path.encode(),'query_string':b'', 'headers':headers,
                'client':('127.0.0.1',1234),'server':('127.0.0.1',80),'root_path':''}
            messages = []
            async def receive(): return {'type':'http.request','body':raw,'more_body':False}
            async def send(message): messages.append(message)
            await self.app(scope, receive, send)
            status = next(m['status'] for m in messages if m['type']=='http.response.start')
            body = b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body')
            return status, json.loads(body)
        return asyncio.run(invoke())

    def test_prepare_requires_token_origin_and_shared_queue(self):
        payload = {'s':'synthetic-session','temperatura':50}
        self.assertEqual(self.request('/api/nidus/consenso',payload,token='')[0],403)
        self.assertEqual(self.request('/api/nidus/consenso',payload,origin='https://external.invalid')[0],403)
        self.assertEqual(self.queue.events,[])
        status, result = self.request('/api/nidus/consenso',payload)
        self.assertEqual(status,200)
        self.assertEqual(result['approval_status'],'UNAPPROVED')
        self.assertEqual(self.queue.events,['enqueue','lease','finish'])

    def test_failed_edit_save_preserves_the_previous_candidate(self):
        self.request('/api/nidus/consenso',{'s':'synthetic-session','temperatura':50})
        previous = self.sessions['synthetic-session']['candidato']
        bits = previous.packed.bits.copy()
        with patch('neuro_rt.nidus_geometry.NidusCandidate.save',side_effect=PermissionError('synthetic')):
            status, _ = self.request('/api/nidus/consenso/editar',{'s':'synthetic-session','eixo':0,
                'indice':2,'pontos':[[0,0],[.4,0],[.4,.4],[0,.4]],'operacao':'add'})
        self.assertEqual(status,409)
        self.assertIs(self.sessions['synthetic-session']['candidato'],previous)
        np.testing.assert_array_equal(previous.packed.bits,bits)

    def test_payload_cannot_select_a_source_path_or_export_unverified_reference(self):
        self.assertEqual(self.request('/api/nidus/consenso',{'s':'synthetic-session',
            'temperatura':50,'path':'C:/untrusted'})[0],400)
        self.assertEqual(self.request('/api/nidus/consenso/exportar',{'s':'synthetic-session',
            'temperatura':50,'editado':False})[0],409)

    def test_prepare_persists_and_publishes_before_releasing_its_lease(self):
        from neuro_rt.nidus_geometry import NidusCandidate
        save = NidusCandidate.save
        def inspected(candidate, folder, **kwargs):
            self.assertEqual(self.queue.events[-1], 'lease')
            return save(candidate, folder, **kwargs)
        with patch.object(NidusCandidate, 'save', inspected):
            status, _ = self.request('/api/nidus/consenso',{'s':'synthetic-session','temperatura':50})
        self.assertEqual(status,200)
        self.assertEqual(self.queue.events[-1],'finish')

    def test_cancelled_prepare_and_failed_persistence_preserve_previous_candidate(self):
        self.request('/api/nidus/consenso',{'s':'synthetic-session','temperatura':50})
        previous = self.sessions['synthetic-session']['candidato']
        self.queue.is_cancelled = True
        status, _ = self.request('/api/nidus/consenso',{'s':'synthetic-session','temperatura':30})
        self.assertEqual(status,409)
        self.assertIs(self.sessions['synthetic-session']['candidato'],previous)
        self.queue.is_cancelled = False
        with patch('neuro_rt.nidus_geometry.NidusCandidate.save',side_effect=PermissionError('synthetic')):
            status, _ = self.request('/api/nidus/consenso',{'s':'synthetic-session','temperatura':30})
        self.assertEqual(status,409)
        self.assertIs(self.sessions['synthetic-session']['candidato'],previous)

    def test_cancelled_export_does_not_publish_an_artifact(self):
        self.sessions['synthetic-session']['source_signature']='synthetic'
        service=self.app.state.neuro_rt
        self.app=FastAPI();self.app.state.neuro_rt=service
        def cancelled(*args,**kwargs):
            self.queue.is_cancelled=True
            kwargs['checkpoint']()
        with patch('neuro_rt.nidus_geometry.export_candidate',cancelled):
            attach_consensus_api(self.app,self.sessions,lambda b:(self.root,'synthetic-uid'))
            status,_=self.request('/api/nidus/consenso/exportar',{'s':'synthetic-session',
                'temperatura':50,'editado':False})
        self.assertEqual(status,409)
        self.assertTrue(self.queue.is_cancelled)
        self.assertFalse(self.sessions['synthetic-session'].get('exportacoes'))

    def test_physical_brush_requires_current_candidate_and_revision_and_can_undo(self):
        _, prepared = self.request('/api/nidus/consenso', {'s':'synthetic-session','temperatura':50})
        before = self.sessions['synthetic-session']['candidato'].packed.bits.copy()
        payload = {'s':'synthetic-session', 'candidate':prepared['candidate'], 'revision':prepared['revision'],
                   'eixo':0, 'indice':2, 'pontos':[[.05,.05]], 'operacao':'add', 'raio_mm':1.5}
        self.assertEqual(self.request('/api/nidus/consenso/pincel', dict(payload, revision=999))[0], 409)
        self.assertEqual(self.request('/api/nidus/consenso/pincel', dict(payload, candidate='old'))[0], 409)
        status, edited = self.request('/api/nidus/consenso/pincel', payload)
        self.assertEqual(status, 200, edited)
        self.assertGreater(edited['brush']['changed_voxels'], 0)
        self.assertGreater(edited['revision'], prepared['revision'])
        self.assertTrue(edited['undo_available'])
        self.assertEqual(self.request('/api/nidus/consenso/pincel', payload)[0], 409)
        status, undone = self.request('/api/nidus/consenso/pincel/desfazer',
            {key: edited[key] for key in ('candidate','revision')} | {'s':'synthetic-session'})
        self.assertEqual(status, 200, undone)
        np.testing.assert_array_equal(self.sessions['synthetic-session']['candidato'].packed.bits, before)

    def test_failed_brush_save_keeps_original_candidate_and_revision(self):
        _, prepared = self.request('/api/nidus/consenso', {'s':'synthetic-session','temperatura':50})
        previous = self.sessions['synthetic-session']['candidato']
        bits = previous.packed.bits.copy()
        payload = {'s':'synthetic-session', 'candidate':prepared['candidate'], 'revision':prepared['revision'],
                   'eixo':0, 'indice':2, 'pontos':[[.05,.05]], 'operacao':'add', 'raio_mm':1.5}
        with patch('neuro_rt.nidus_geometry.NidusCandidate.save', side_effect=PermissionError('synthetic')):
            self.assertEqual(self.request('/api/nidus/consenso/pincel', payload)[0], 409)
        self.assertIs(self.sessions['synthetic-session']['candidato'], previous)
        np.testing.assert_array_equal(previous.packed.bits, bits)

    def test_consensus_mesh_is_revision_bound_and_cached_without_editing_mask(self):
        from neuro_rt.nidus_consensus_mesh import candidate_mesh
        _, prepared = self.request('/api/nidus/consenso', {'s':'synthetic-session','temperatura':50})
        original = self.sessions['synthetic-session']['candidato'].packed.bits.copy()
        payload = {'s':'synthetic-session', 'candidate':prepared['candidate'], 'revision':prepared['revision']}
        queue_before = list(self.queue.events)
        with patch('neuro_rt.nidus_consensus_mesh.candidate_mesh', wraps=candidate_mesh) as mesh:
            status, first = self.request('/api/nidus/consenso/malha', payload)
            self.assertEqual(status, 200, first)
            status, second = self.request('/api/nidus/consenso/malha', payload)
            self.assertEqual(status, 200, second)
            self.assertEqual(first['url'], second['url'])
            self.assertEqual(mesh.call_count, 1)
        self.assertEqual(self.queue.events, queue_before, 'Read-only 3D preview must not enter the segmentation queue')
        self.assertEqual(first['coordinate_system'], 'LPS_mm')
        self.assertGreater(first['triangles'], 0)
        self.assertIn('/api/nidus/consenso/malha/download?', first['url'])
        self.assertEqual(first['revision'], prepared['revision'])
        np.testing.assert_array_equal(self.sessions['synthetic-session']['candidato'].packed.bits, original)
        self.assertEqual(self.request('/api/nidus/consenso/malha', dict(payload, revision=999))[0], 409)
        status, binary = self.get_binary(first['url'])
        self.assertEqual(status, 200)
        self.assertEqual(struct.unpack('<I', binary[80:84])[0], first['triangles'])
        self.request('/api/nidus/consenso/pincel', payload | {
            'eixo':0, 'indice':2, 'pontos':[[.05,.05]], 'operacao':'add', 'raio_mm':1.5})
        self.assertEqual(self.get_binary(first['url'])[0], 404, 'Old geometry must not survive a changed contour')

    def get_binary(self, url):
        parsed = urlsplit(url)
        async def invoke():
            scope = {'type':'http','http_version':'1.1','method':'GET','scheme':'http',
                'path':parsed.path,'raw_path':parsed.path.encode(),'query_string':parsed.query.encode(),
                'headers':[(b'host',b'127.0.0.1')], 'client':('127.0.0.1',1234),
                'server':('127.0.0.1',80),'root_path':''}
            messages = []
            async def receive(): return {'type':'http.request','body':b'','more_body':False}
            async def send(message): messages.append(message)
            await self.app(scope, receive, send)
            return (next(m['status'] for m in messages if m['type']=='http.response.start'),
                    b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body'))
        return asyncio.run(invoke())

    def test_joint_export_freezes_native_nidus_and_only_uses_eligible_same_exam_anatomy(self):
        service = self.app.state.neuro_rt
        service.testing_access = SimpleNamespace(allowed=lambda request, tool: tool == 'nidus')
        self.sessions['synthetic-session']['source_signature'] = 'fixed-reference-signature'
        self.app = FastAPI()
        self.app.state.neuro_rt = service
        root = '/api/nidus/consenso'
        selected = {'id': 'anatomy_synthseg', 'groups': ['anatomia'],
                    'eligibility': {'selectable': True},
                    'bindings': [{'role': 'T1', 'series_ticket': 'same-exam'}]}
        captured = {}

        def describe(ticket, _host):
            return SimpleNamespace(ticket=ticket, subject_key='same-subject', modality='MR',
                source_format='dicom', study_key='different-study' if ticket == 'other-exam' else 'same-study')

        def selection(tickets, category):
            self.assertEqual(tickets, ['synthetic-ticket', 'same-exam'])
            self.assertEqual(category, 'anatomia')
            return {'models': [selected, dict(selected, id='glioma_model', groups=['glioma'])]}

        def submit(payload, *, nidus_snapshot):
            self.assertEqual(self.queue.events[-1], 'finish', 'Do not enqueue inside the Nidus lease')
            item = payload['studies'][0]
            self.assertEqual(item['reference'], 'synthetic-ticket')
            self.assertEqual(item['bindings_by_model'], {'anatomy_synthseg': selected['bindings']})
            self.assertTrue(payload['export_rtstruct'])
            path = Path(nidus_snapshot['mask_path'])
            self.assertTrue(path.is_relative_to(self.root / 'nidus'))
            image = sitk.ReadImage(str(path))
            original = self.sessions['synthetic-session']['consenso'].mask(50)
            np.testing.assert_array_equal(sitk.GetArrayFromImage(image), original)
            self.assertEqual(nidus_snapshot['source_signature'], 'fixed-reference-signature')
            captured.update(path=path, study_id=item['study_id'])

        service.studies = SimpleNamespace(selection=selection, submit=submit)
        with patch('neuro_rt.series_selection.describe_series', describe), \
                patch('neuro_rt.nidus_geometry.source_signature', return_value='fixed-reference-signature'):
            attach_consensus_api(self.app, self.sessions, lambda b: (self.root, 'synthetic-uid'))
        status, choices = self.request(root+'/anatomia', {
            's': 'synthetic-session', 'bilhetes': ['same-exam', 'other-exam']})
        self.assertEqual(status, 200)
        self.assertEqual([model['id'] for model in choices['models']], ['anatomy_synthseg'])
        payload = {'s': 'synthetic-session', 'temperatura': 50, 'editado': False,
                   'selection': choices['selection'], 'modelos': ['anatomy_synthseg']}
        self.assertEqual(self.request(root+'/exportar-com-anatomia', dict(payload, selection='stale'))[0], 409)
        self.assertEqual(self.request(root+'/exportar-com-anatomia', dict(payload, modelos=['glioma_model']))[0], 409)
        status, result = self.request(root+'/exportar-com-anatomia', payload)
        self.assertEqual(status, 202)
        self.assertEqual(result['study_id'], captured['study_id'])
        self.assertEqual(result['approval_status'], 'UNAPPROVED')
        self.assertFalse(captured['path'].exists(), 'Submit owns the immutable copy after it returns')


if __name__ == '__main__': unittest.main()

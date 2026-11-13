"""Jobs are bounded, use opaque tickets, and never mutate static NIDUS state."""
import io
import asyncio
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import sys

from fastapi import FastAPI
import numpy as np
import pydicom
from pydicom.uid import generate_uid
from PIL import Image

from test_nidus_temporal import classic


class TestClient:
    """Minimal in-process ASGI client, without adding httpx to the app runtime."""
    def __init__(self, app):
        self.app = app

    def request(self, method, path, json=None):
        raw = __import__('json').dumps(json).encode() if json is not None else b''
        messages = []
        received = False
        async def receive():
            nonlocal received
            if received:
                await asyncio.Event().wait()
            received = True
            return {'type': 'http.request', 'body': raw, 'more_body': False}
        async def send(message):
            messages.append(message)
        asyncio.run(self.app({'type': 'http', 'asgi': {'version': '3.0'},
                             'http_version': '1.1', 'method': method, 'scheme': 'http',
                             'path': path, 'raw_path': path.encode(), 'root_path': '',
                             'query_string': b'', 'headers': [(b'content-type', b'application/json')],
                             'server': ('testserver', 80), 'client': ('127.0.0.1', 1)}, receive, send))
        start = next(m for m in messages if m['type'] == 'http.response.start')
        class Response:
            status_code = start['status']
            headers = {k.decode(): v.decode() for k, v in start['headers']}
            content = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
            text = content.decode(errors='replace')
            def json(self):
                return __import__('json').loads(self.content)
        return Response()

    def get(self, path):
        return self.request('GET', path)

    def post(self, path, json=None):
        return self.request('POST', path, json)


class TemporalAPI(unittest.TestCase):
    def setUp(self):
        from neuro_rt.nidus_temporal_api import attach_temporal
        self.temp = tempfile.TemporaryDirectory()
        self.sources = classic(Path(self.temp.name))
        self.seen = []
        self.lock = threading.Lock()
        def resolver(ticket, origin):
            return (self.temp.name, self.sources[0]['uid']) if ticket == 'known' else (None, None)
        def renderer(data, params, scale):
            self.assertTrue(self.lock.locked(), 'CINE must share the static projection lock')
            self.seen.append(dict(scale))
            buffer = io.BytesIO()
            Image.fromarray(np.full((8, 8), int(data.array.mean()), dtype='uint8')).save(buffer, format='PNG')
            return buffer.getvalue(), {'center': 150, 'width': 300}
        self.app = FastAPI()
        self.service = attach_temporal(self.app, resolver, projection_lock=self.lock, renderer=renderer)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def group(self):
        response = self.client.post('/api/nidus/temporal/discover', json={'itens': [{'bilhete': 'known', 'origem': 'pasta'}]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn(self.temp.name, response.text)
        self.assertNotIn(self.sources[0]['uid'], response.text)
        return response.json()['groups'][0]['id']

    def wait(self, job):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            status = self.client.get('/api/nidus/temporal/status/' + job).json()
            if status['state'] in ('ready', 'failed', 'cancelled'):
                return status
            time.sleep(.01)
        self.fail('job did not finish')

    def test_real_frames_prepared_once_with_identical_window_and_reusable_pngs(self):
        group = self.group()
        response = self.client.post('/api/nidus/temporal/prepare', json={'group': group, 'lado': 1024, 'laje': None, 'caixa': None})
        self.assertEqual(response.status_code, 200, response.text)
        job = response.json()['job']
        status = self.wait(job)
        self.assertEqual(status['state'], 'ready', status)
        self.assertTrue(status['can_play'])
        self.assertEqual(status['ready_count'], 3)
        self.assertEqual(len(self.seen), 3)
        self.assertTrue(all(s == self.seen[0] for s in self.seen))
        images = [self.client.get('/api/nidus/temporal/frame/%s/%d' % (job, i)) for i in range(3)]
        self.assertTrue(all(r.status_code == 200 and r.headers['content-type'] == 'image/png' for r in images))
        self.assertLess(np.asarray(Image.open(io.BytesIO(images[0].content))).mean(),
                        np.asarray(Image.open(io.BytesIO(images[2].content))).mean())
        self.client.get('/api/nidus/temporal/frame/%s/0' % job)
        self.assertEqual(len(self.seen), 3, 'playback must never reload/re-render a phase')
        self.assertFalse(hasattr(self.app, '_ABERTA'))

    def test_request_cannot_supply_paths_or_unregistered_ids(self):
        response = self.client.post('/api/nidus/temporal/discover', json={'itens': [{'bilhete': 'known', 'folder': self.temp.name}]})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(self.temp.name, response.text)
        response = self.client.post('/api/nidus/temporal/prepare', json={'group': 'guessed'})
        self.assertEqual(response.status_code, 404)
        response = self.client.post('/api/nidus/temporal/discover', json={'itens': [{'bilhete': 'unknown'}]})
        self.assertEqual(response.status_code, 422)

    def test_anchor_must_be_a_source_member_of_the_selected_temporal_group(self):
        static_uid = generate_uid()
        source_path = Path(self.temp.name) / 'p0-z0.dcm'
        ds = pydicom.dcmread(source_path)
        ds.SeriesInstanceUID, ds.SOPInstanceUID = static_uid, generate_uid()
        ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
        ds.SeriesDescription, ds.ProtocolName = 'AXI 3D TOF 3SLAB FS MT ASSET', '3D TOF'
        del ds.TemporalPositionIdentifier
        del ds.NumberOfTemporalPositions
        ds.save_as(Path(self.temp.name) / 'static-tof.dcm', enforce_file_format=True)
        uids = {'known': self.sources[0]['uid'], 'static': static_uid}
        self.service.resolver = lambda ticket, origin: (self.temp.name, uids[ticket])
        rows = [{'bilhete': 'known'}, {'bilhete': 'static'}]
        response = self.client.post('/api/nidus/temporal/discover',
                                    json={'itens': rows, 'ancora': {'bilhete': 'static'}})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['groups'], [], 'A static selection must not open another series cine')
        response = self.client.post('/api/nidus/temporal/discover',
                                    json={'itens': rows, 'ancora': {'bilhete': 'known'}})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()['groups']), 1)

    def test_folder_inventory_may_find_real_cine_beside_static_tof_without_switching_reference(self):
        static_uid = generate_uid()
        ds = pydicom.dcmread(Path(self.temp.name) / 'p0-z0.dcm')
        ds.SeriesInstanceUID, ds.SOPInstanceUID = static_uid, generate_uid()
        ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
        ds.SeriesDescription, ds.ProtocolName = 'SYNTHETIC TOF', '3D TOF'
        del ds.TemporalPositionIdentifier
        del ds.NumberOfTemporalPositions
        ds.save_as(Path(self.temp.name) / 'static.dcm', enforce_file_format=True)
        mapping = {'known': (self.temp.name, self.sources[0]['uid']), 'static': (self.temp.name, static_uid)}
        self.service.resolver = lambda ticket, origin: mapping[ticket]
        body = {'itens':[{'bilhete':'known'}, {'bilhete':'static'}], 'ancora':{'bilhete':'static'}}
        response = self.client.post('/api/nidus/temporal/folder-discover', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        groups = response.json()['groups']
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['series_tickets'], [{'bilhete':'known', 'origem':'pasta'}])
        self.assertNotIn('SYNTHETIC TOF', groups[0]['label'])
        self.assertNotIn(self.temp.name, response.text)
        self.assertEqual(self.client.post('/api/nidus/temporal/discover', json=body).json()['groups'], [])
        # A small Enhanced/single-file series may not have appeared in the old picker.
        body['itens'] = [{'bilhete':'static'}]
        response = self.client.post('/api/nidus/temporal/folder-discover', json=body)
        self.assertEqual(len(response.json()['groups']), 1)
        self.assertEqual(response.json()['groups'][0]['series_tickets'], [])

    def test_folder_inventory_requires_study_anchor_and_excludes_other_subjects(self):
        self.assertEqual(self.client.post('/api/nidus/temporal/folder-discover',
            json={'itens':[{'bilhete':'known'}]}).status_code, 422)
        with tempfile.TemporaryDirectory() as other:
            sources = classic(Path(other), patient='SYNTHETIC_OTHER')
            mapping = {'known': (self.temp.name, self.sources[0]['uid']), 'other': (other, sources[0]['uid'])}
            self.service.resolver = lambda ticket, origin: mapping[ticket]
            response = self.client.post('/api/nidus/temporal/folder-discover', json={
                'itens':[{'bilhete':'known'}, {'bilhete':'other'}], 'ancora':{'bilhete':'known'}})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(len(response.json()['groups']), 1)
            self.assertEqual(response.json()['groups'][0]['series_tickets'], [{'bilhete':'known', 'origem':'pasta'}])

    def test_cancel_prevents_late_pixels_from_becoming_playable(self):
        group = self.group()
        self.lock.acquire()
        try:
            job = self.client.post('/api/nidus/temporal/prepare', json={'group': group}).json()['job']
            response = self.client.post('/api/nidus/temporal/cancel/' + job)
            self.assertEqual(response.status_code, 200)
        finally:
            self.lock.release()
        status = self.wait(job)
        self.assertEqual(status['state'], 'cancelled')
        self.assertFalse(status['can_play'])
        self.assertEqual(self.client.get('/api/nidus/temporal/frame/%s/0' % job).status_code, 409)

    def test_renderer_exception_is_sanitized(self):
        group = self.group()
        def fail(*args):
            raise ValueError('SYNTHETIC_A ' + self.temp.name)
        self.service.renderer = fail
        job = self.client.post('/api/nidus/temporal/prepare', json={'group': group}).json()['job']
        status = self.wait(job)
        self.assertEqual(status['state'], 'failed')
        self.assertEqual(status['error']['code'], 'PROCESSING_FAILED')
        self.assertNotIn(self.temp.name, json.dumps(status))

    def test_pixel_limit_does_not_report_partial_playback_as_ready(self):
        self.service.max_png_bytes = 10
        group = self.group()
        job = self.client.post('/api/nidus/temporal/prepare', json={'group': group}).json()['job']
        status = self.wait(job)
        self.assertEqual(status['state'], 'failed')
        self.assertEqual(status['error']['code'], 'RESOURCE_LIMIT')
        self.assertFalse(status['can_play'])

    def test_processing_deadline_and_expired_registry_release_data(self):
        self.service.max_seconds = -1
        group = self.group()
        job = self.client.post('/api/nidus/temporal/prepare', json={'group': group}).json()['job']
        status = self.wait(job)
        self.assertEqual(status['error']['code'], 'TIMEOUT')
        self.service.ttl = -1
        self.assertEqual(self.client.get('/api/nidus/temporal/status/' + job).status_code, 404)
        self.assertFalse(self.service.jobs)
        self.assertFalse(self.service.groups)

    def test_identical_prepare_reuses_completed_job(self):
        group = self.group()
        job = self.client.post('/api/nidus/temporal/prepare', json={'group': group}).json()['job']
        self.wait(job)
        again = self.client.post('/api/nidus/temporal/prepare', json={'group': group}).json()['job']
        self.assertEqual(job, again)
        self.assertEqual(len(self.seen), 3)

    def test_actual_projector_1024_uses_group_window_and_native_geometry(self):
        from neuro_rt import nidus_temporal as temporal
        from neuro_rt.nidus_temporal_api import render_frame, _view
        root = Path(__file__).resolve().parents[1]
        recon = Path(os.environ.get('RADAI_RECON_APP', str(root.parent / 'radai-suite-release-v816' / '_montagem/componentes/RECON_3D/app')))
        if not (recon / 'radai_projection.py').is_file():
            self.skipTest('Set RADAI_RECON_APP to the shared RECON_3D app for the native projection smoke')
        sys.path[:0] = [str(root / 'app'), str(recon)]
        import radai_nidus as N
        group = temporal.discover(self.sources).groups[0]
        data = temporal.load_frame(group, 2)
        # A small bright vessel in the synthetic phantom, not a uniform solid block.
        data.array[1, 2, 3] = 1000
        scale = temporal.shared_scale([temporal.sample_values(temporal.load_frame(group, i)) for i in range(2)] +
                                      [temporal.sample_values(data)])
        image = data.image()
        self.assertEqual(image.GetSize(), (6, 5, 3))
        self.assertEqual(image.GetSpacing(), (.7, .8, 2.))
        with self.lock:
            png, window = render_frame(data, _view({'group': group.id}, 'volume3d'), scale)
        decoded = Image.open(io.BytesIO(png))
        self.assertEqual(decoded.size, (1024, 1024))
        center, width = N.janela_de('angio', scale)
        self.assertEqual(window, {'center': center, 'width': width})
        self.assertGreater(np.asarray(decoded).max(), 0)

    def test_derived_mip_default_render_keeps_two_dimensions(self):
        from neuro_rt import nidus_temporal as temporal
        from neuro_rt.nidus_temporal_api import render_frame, _view
        root = Path(__file__).resolve().parents[1]
        recon = Path(os.environ.get('RADAI_RECON_APP', str(root.parent / 'radai-suite-release-v816' / '_montagem/componentes/RECON_3D/app')))
        if not (recon / 'radai_projection.py').is_file():
            self.skipTest('Shared projection library unavailable')
        sys.path[:0] = [str(root / 'app'), str(recon)]
        with tempfile.TemporaryDirectory() as temp:
            group = temporal.discover(classic(Path(temp), projection=True)).groups[0]
            data = temporal.load_frame(group, 2)
            scale = temporal.shared_scale([temporal.sample_values(data)])
            with self.lock:
                png, _ = render_frame(data, _view({'group': group.id}, 'projection2d'), scale)
            self.assertEqual(Image.open(io.BytesIO(png)).format, 'PNG')
            with self.assertRaises(temporal.TemporalError):
                _view({'group': group.id, 'lao': 10}, 'projection2d')


if __name__ == '__main__':
    unittest.main()

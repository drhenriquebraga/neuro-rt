import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

HOST_APP = Path(os.environ.get('NEURO_TEST_HOST_APP', Path(__file__).resolve().parents[2] / 'AUTO_CONTORNO' / 'app'))


class SharedQueueTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(HOST_APP))
        self.Q = importlib.import_module('radai_queue')
        self.host = importlib.import_module('radai_queue_state')
        self.bridge_module = importlib.import_module('integration.queue_bridge')
        self.tmp = tempfile.TemporaryDirectory(prefix='neuro_shared_queue_')
        self.env = patch.dict(os.environ, {'RADAI_FILA_DIR': self.tmp.name,
                                           'RADAI_CALIB_DIR': self.tmp.name,
                                           'LOCALAPPDATA': self.tmp.name})
        self.env.start()
        self.host._CARDS[:] = []
        self.host._NEURO_CANCEL.clear()
        self.host._VEZ.update(dono=None, ticket=None, lote_quer=False, desde=0.0)
        self.host._PERSISTIR.update(ligada=False, erro='', gravacoes=0)
        self.host.pedir_fechar_ao_fim(False)
        self.host.pausar_neuro(False)
        self.sync = patch.object(self.host, '_sincroniza', return_value=False)
        self.sync.start()
        self.host.carregar()
        self.bridge = self.bridge_module.QueueBridge(self.host, poll_interval=0.005)

    def tearDown(self):
        if hasattr(self, 'bridge'):
            self.bridge.close()
        if hasattr(self, 'sync'):
            self.sync.stop()
            self.env.stop()
            self.tmp.cleanup()
        if str(HOST_APP) in sys.path:
            sys.path.remove(str(HOST_APP))

    def item(self, suffix='a'):
        return {'study_id': 'study-' + suffix, 'reference': 'ticket-' + suffix,
                'model_ids': ['MRI_GBM'], 'bindings_by_model': {},
                'legacy_input_path': 'C:/PRIVATE_SYNTHETIC/path'}

    def enqueue(self, suffix='a'):
        return self.bridge.enqueue_study('request-' + suffix, self.item(suffix))

    def wait_for(self, predicate):
        deadline = time.monotonic() + 2
        while not predicate():
            if time.monotonic() >= deadline:
                self.fail('coordinator did not reach expected state')
            time.sleep(0.005)

    def test_idempotent_concurrent_submissions_share_host_card(self):
        tickets = []
        threads = [threading.Thread(target=lambda: tickets.append(self.enqueue())) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(2)
        self.assertEqual(8, len(tickets))
        self.assertEqual(1, len({t.id for t in tickets}))
        self.assertEqual(1, len(self.host.cards()))
        self.assertEqual('neuro', self.host.cards()[0]['executor'])
        self.assertEqual([], self.host.series_esperando())
        self.assertIsNone(self.host.proxima_esperando())
        self.assertTrue(self.host.ha_manual_esperando())

    def test_waits_for_lote_then_blocks_lote_and_vigia(self):
        self.assertTrue(self.host.tentar_a_vez('lote'))
        ticket = self.enqueue()
        acquired = threading.Event()
        release = threading.Event()
        def run():
            with self.bridge.await_turn(ticket, threading.Event()):
                acquired.set()
                release.wait(2)
        thread = threading.Thread(target=run)
        thread.start()
        time.sleep(0.03)
        self.assertFalse(acquired.is_set())
        self.host.soltar_a_vez('lote')
        self.assertTrue(acquired.wait(2))
        self.assertFalse(self.host.tentar_a_vez('lote'))
        self.assertFalse(self.host.tentar_a_vez('vigia'))
        release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual('pronto', self.host.cartao(ticket.id)['estado'])
        self.assertTrue(self.host.tentar_a_vez('vigia'))

    def test_two_neuro_waiters_are_exclusive_and_manual_beats_vigia_turno(self):
        self.host.vigia_na_fila([{'uid': 'synthetic-vigia'}])
        self.host.overnight()
        self.host.autorizar_turno()
        tickets = [self.enqueue('a'), self.enqueue('b')]
        self.assertFalse(self.host.turno_na_vez())
        self.assertFalse(self.host.tentar_a_vez('vigia'))
        active = []
        maximum = []
        lock = threading.Lock()
        def run(ticket):
            with self.bridge.await_turn(ticket, threading.Event()):
                with lock:
                    active.append(ticket.id)
                    maximum.append(len(active))
                time.sleep(0.025)
                with lock:
                    active.remove(ticket.id)
        threads = [threading.Thread(target=run, args=(t,)) for t in reversed(tickets)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(1, max(maximum))
        self.assertTrue(self.host.turno_na_vez())

    def test_cancel_active_signals_worker_but_keeps_possession_until_finish(self):
        ticket = self.enqueue()
        stop = threading.Event()
        lease = self.bridge.await_turn(ticket, stop)
        self.host.cancel_neuro(ticket.id)
        self.assertTrue(stop.is_set())
        self.assertFalse(self.host.tentar_a_vez('neuro'))
        self.host.soltar_a_vez('neuro')
        self.assertFalse(self.host.tentar_a_vez('lote'))
        lease.finish('cancelled')
        self.assertEqual('cancelado', self.host.cartao(ticket.id)['estado'])
        self.assertIsNone(self.host.quem_tem_a_vez()['dono'])

    def test_cancel_waiter_and_error_release_ownership(self):
        ticket = self.enqueue()
        stop = threading.Event()
        stop.set()
        with self.assertRaises(self.bridge_module.QueueCancelled):
            self.bridge.await_turn(ticket, stop)
        self.assertEqual('cancelado', self.host.cartao(ticket.id)['estado'])
        ticket = self.enqueue('b')
        with self.assertRaisesRegex(RuntimeError, 'synthetic'):
            with self.bridge.await_turn(ticket, threading.Event()):
                raise RuntimeError('synthetic')
        self.assertEqual('falhou', self.host.cartao(ticket.id)['estado'])
        self.assertIsNone(self.host.quem_tem_a_vez()['dono'])

    def test_update_barrier_and_status_observe_neuro(self):
        updater = importlib.import_module('radai_atualizar')
        ticket = self.enqueue()
        lease = self.bridge.await_turn(ticket, threading.Event())
        self.assertEqual(updater.SEGURA_NEURO, updater.o_que_segura({}))
        self.host.pedir_fechar_ao_fim(True)
        self.assertFalse(self.host.tentar_a_vez('vigia'))
        lease.finish('completed')
        self.assertIsNone(updater.o_que_segura({}))
        self.assertFalse(self.host.tentar_a_vez('lote'))
        ticket2 = self.enqueue('b')
        self.assertFalse(self.host.try_neuro_turn(ticket2.id))
        self.host.pedir_fechar_ao_fim(False)
        with self.bridge.await_turn(ticket2, threading.Event()):
            pass

    def test_explicit_update_interrupt_waits_for_worker_acknowledgement(self):
        updater = importlib.import_module('radai_atualizar')
        ticket = self.enqueue()
        stop = threading.Event()
        lease = self.bridge.await_turn(ticket, stop)
        returned = threading.Event()
        with patch.dict(updater._CTX, {'cancelar': False}), \
                patch.object(updater, 'INTERVALO_DA_ESPERA_S', 0.005):
            thread = threading.Thread(target=lambda: (updater._interromper_neuro(), returned.set()))
            thread.start()
            self.assertTrue(stop.wait(2))
            self.assertFalse(returned.is_set())
            self.assertFalse(self.host.tentar_a_vez('vigia'))
            lease.finish('cancelled')
            self.assertTrue(returned.wait(2))
            thread.join(2)

    def test_pause_blocks_next_worker_and_terminal_card_can_be_dismissed(self):
        ticket = self.enqueue()
        lease = self.bridge.await_turn(ticket, threading.Event())
        self.host.pausar_neuro(True)
        lease.finish('completed')
        self.assertFalse(self.host.tentar_a_vez('vigia'))
        self.assertFalse(self.host.tentar_a_vez('lote'))
        self.host.pausar_neuro(False)
        self.assertTrue(self.host.tirar(ticket.id))
        self.assertIsNone(self.host.cartao(ticket.id))

    def test_persistence_sanitized_and_restart_does_not_restart_worker(self):
        ticket = self.enqueue()
        lease = self.bridge.await_turn(ticket, threading.Event())
        self.bridge.report(ticket, {'stage': 'running', 'fraction': 0.5,
                                    'message': 'SECRET_SYNTHETIC', 'path': 'C:/PRIVATE'})
        for path in Path(self.tmp.name).glob('*.json'):
            content = path.read_text(encoding='utf-8')
            self.assertNotIn('PRIVATE', content)
            self.assertNotIn('SECRET_SYNTHETIC', content)
            self.assertNotIn('study-a', content)
        self.host._CARDS[:] = []
        self.host._VEZ.update(dono=None, ticket=None)
        self.host.carregar()
        card = self.host.cartao(ticket.id)
        self.assertEqual('falhou', card['estado'])
        self.assertEqual('neuro', card['executor'])
        self.assertEqual(ticket.id, self.enqueue().id)
        lease.finish('failed')

    def test_running_vigia_and_arriving_lote_wait_for_neuro_exclusively(self):
        self.assertTrue(self.host.tentar_a_vez('vigia'))
        ticket = self.enqueue()
        self.assertFalse(self.host.try_neuro_turn(ticket.id))
        self.host.soltar_a_vez('vigia')
        lease = self.bridge.await_turn(ticket, threading.Event())
        self.host.acrescentar_series([{'uid': 'synthetic-lote', 'pasta': self.tmp.name}])
        acquired = threading.Event()
        def lote():
            self.host.esperar_a_vez('lote', passo_s=0.005)
            acquired.set()
            self.host.soltar_a_vez('lote')
        thread = threading.Thread(target=lote)
        thread.start()
        time.sleep(0.03)
        self.assertFalse(acquired.is_set())
        lease.finish('completed')
        self.assertTrue(acquired.wait(2))
        thread.join(2)

    def test_changed_idempotency_payload_rejected(self):
        ticket = self.enqueue()
        item = self.item()
        item['model_ids'] = ['MRI_Meningioma']
        with self.assertRaises(ValueError):
            self.bridge.enqueue_study('request-a', item)
        item = self.item()
        item['legacy_input_path'] = 'C:/DIFFERENT_SYNTHETIC'
        with self.assertRaises(ValueError):
            self.bridge.enqueue_study('request-a', item)
        self.assertEqual(ticket.id, self.enqueue().id)

    def test_queue_http_routes_preserve_card_cancel_and_neuro_controls(self):
        import types
        routes = {}
        class App:
            def get(self, path):
                return self.post(path)
            def post(self, path):
                def register(function):
                    routes[path] = function
                    return function
                return register
        with patch.dict(sys.modules, {'fastapi': types.SimpleNamespace(Request=object)}):
            self.host.montar(App())
        self.assertEqual('_cancelar', routes['/api/fila/cancelar'].__name__)
        self.assertEqual('_cancelar_neuro_atual', routes['/api/fila/neuro/cancelar'].__name__)
        self.assertIn('/api/fila/neuro/pausar', routes)


if __name__ == '__main__':
    unittest.main()

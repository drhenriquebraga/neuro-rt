"""Host queue reservation precedes the external lifecycle handoff."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.build_host_bootstrap import generate


class ExternalProviderTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        base = root / 'runtime/test-tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.module_patch = patch.dict(sys.modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        for name in list(sys.modules):
            if name.startswith('_radai_neuro_bootstrap'):
                sys.modules.pop(name)
        path = generate(self.root / 'bootstrap.py')
        spec = importlib.util.spec_from_file_location('external_provider_fixture', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.owner = {'dono': None}
        self.events = []
        self.held = False
        queue = SimpleNamespace(quem_tem_a_vez=lambda: dict(self.owner),
            fechando_ao_fim=lambda: self.held, pedir_fechar_ao_fim=self.hold,
            cancelar_neuro_ativo=lambda: self.events.append('cancel_neuro'))
        updater = SimpleNamespace(etapa=lambda: 'idle', EM_ANDAMENTO=set(),
            _status=lambda: {}, o_que_segura=lambda _: [])
        sys.modules.update(radai_queue_state=queue, radai_atualizar=updater)
        self.handoff = Mock(side_effect=lambda plan: (self.events.append('handoff') or {'ok': True, 'scheduled': True}))
        release = {'state': 'available', 'release_id': 23, 'asset_id': 7,
            'version': '1.1.0', 'name': 'NEURO_RT_SETUP_v1.1.0.zip', 'size': 1000,
            'url': 'https://api.github.com/repos/drhenriquebraga/neuro-rt/releases/assets/7',
            'sha256': 'a'*64, 'package_kind': 'setup'}
        self.client = SimpleNamespace(check_plugin_release=Mock(return_value=release),
                                      refresh_plugin_release=Mock(return_value=release))
        self.provider = self.module.build_provider(self.root,
            {'version': '8.12', 'python_executable': sys.executable},
            {'neuro_external_install': self.handoff, 'neuro_release_client': self.client})
        policy = self.provider.consent_policy()
        self.provider.accept_consent(dict(accepted=True, version=policy['version'], digest=policy['digest']))
        self.addCleanup(self.finish_workers)

    def finish_workers(self):
        self.owner['dono'] = None
        for worker in threading.enumerate():
            if worker.name == 'neuro-external-handoff':
                worker.join(3)
                self.assertFalse(worker.is_alive())

    def hold(self, held):
        self.held = held
        self.events.append('hold' if held else 'release')

    def wait_handoff(self):
        deadline = time.monotonic() + 3
        while not self.handoff.called and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(self.handoff.called)
        self.finish_workers()

    def test_idle_external_handoff_has_fixed_plan_and_never_legacy_restart(self):
        update = self.module._load_private_installer()
        with patch.object(update.UpdateCoordinator, 'request_plugin_update', side_effect=AssertionError('No old in-process updater')):
            self.provider.request_plugin_update('neuro-rt', 'comecar')
            self.wait_handoff()
        plan = self.handoff.call_args.args[0]
        self.assertEqual(plan['schema'], 'neuro-rt/external-plan/1')
        self.assertEqual(plan['action'], 'install')
        self.assertLess(self.events.index('hold'), self.events.index('handoff'))
        self.assertTrue(self.held)

    def test_wait_and_interrupt_keep_live_child_lease_until_host_confirms_exit(self):
        self.owner['dono'] = 'neuro'
        self.provider.request_plugin_update('neuro-rt', 'interromper')
        self.assertIn('cancel_neuro', self.events)
        self.assertTrue(self.held)
        self.assertEqual(self.owner['dono'], 'neuro')
        self.assertFalse(self.handoff.called)
        self.assertEqual(self.provider.status()['state'], 'waiting')
        self.owner['dono'] = None
        self.wait_handoff()
        self.assertEqual(self.handoff.call_args.args[0]['action'], 'interrupt_then_update')

    def test_explicit_refresh_bypasses_cached_check(self):
        self.provider.refresh_plugin_release('neuro-rt', None)
        self.client.refresh_plugin_release.assert_called_once_with('neuro-rt', None)
        self.client.check_plugin_release.assert_not_called()

    def test_handoff_requires_exact_positive_scheduled_acknowledgement(self):
        self.handoff.side_effect = None
        for result in ({'ok': True}, {'scheduled': True}, {}, {'ok': True, 'scheduled': 1}):
            with self.subTest(result=result):
                self.handoff.return_value = result
                self.provider.request_plugin_update('neuro-rt', 'comecar')
                self.finish_workers()
                self.assertEqual(self.provider.status()['state'], 'failed')
                self.assertFalse(self.held)

    def test_status_write_after_positive_ack_cannot_release_host_reservation(self):
        installer = self.module._load_private_installer().install_state
        atomic = installer._atomic_json
        def deny_restarting(path, value):
            if value.get('state') == 'restarting':
                raise PermissionError('synthetic post-ack status failure')
            return atomic(path, value)
        with patch.object(installer, '_atomic_json', side_effect=deny_restarting):
            self.provider.request_plugin_update('neuro-rt', 'comecar')
            self.wait_handoff()
        self.assertEqual(self.provider.status()['state'], 'restarting')
        self.assertTrue(self.held)
        self.assertNotIn('release', self.events)

    def test_same_host_cannot_schedule_another_helper_after_positive_ack(self):
        self.provider.request_plugin_update('neuro-rt', 'comecar')
        self.wait_handoff()
        self.provider.request_plugin_update('neuro-rt', 'comecar')
        self.finish_workers()
        self.handoff.assert_called_once()
        self.assertTrue(self.held)


if __name__ == '__main__':
    unittest.main()

"""Exercise the real source/generated providers at the host-owned API boundary."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_plugin_install import fixture_package
from scripts.build_host_bootstrap import generate

ROOT = Path(__file__).resolve().parents[1]
HOST_APP = ROOT.parent / 'AUTO_CONTORNO/app'


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UpdateProviderTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.generated = module_at('test_generated_neuro_provider', generate(self.root / 'bootstrap.py'))
        self.source = module_at('test_source_neuro_provider', ROOT / 'integration/update_provider.py')
        self.source.SOURCES = self.generated.SOURCES
        # Each generated revision owns its reviewed, pinned bootstrap package.
        self.bootstrap_modules = {key: value for key, value in sys.modules.items()
                                  if key.startswith('_radai_neuro_bootstrap')}
        for key in self.bootstrap_modules:
            sys.modules.pop(key)
        self.addCleanup(self.restore_bootstrap_modules)

    def restore_bootstrap_modules(self):
        for key in list(sys.modules):
            if key.startswith('_radai_neuro_bootstrap'):
                sys.modules.pop(key)
        sys.modules.update(self.bootstrap_modules)

    def scenario(self, module, flag, active_child=False):
        host = self.root / (module.__name__ + '-' + flag + ('-active' if active_child else ''))
        host.mkdir()
        for name in ('radai_panel.py', 'radai_ui.py', 'entrega.txt'):
            (host / name).write_text('synthetic host')
        state = {'turno_agendado': flag == 'turno_agendado', 'overnight': flag == 'overnight'}
        owner = {'dono': 'neuro' if active_child else None}
        held = [False]
        events = []
        restarted = threading.Event()
        def stop_turn():
            events.append('overnight_interromper')
            state.update(turno_agendado=False, overnight=False)
            return {'ok': True}
        queue = SimpleNamespace(quem_tem_a_vez=lambda: dict(owner),
            fechando_ao_fim=lambda: held[0],
            pedir_fechar_ao_fim=lambda value: held.__setitem__(0, bool(value)),
            cancelar_neuro_ativo=lambda: events.append('cancel_neuro'))
        updater = module_at('test_provider_base_updater', HOST_APP / 'radai_atualizar.py')
        updater._CTX['ler_vigia'] = lambda: dict(state)
        watcher = SimpleNamespace(overnight_interromper=stop_turn)
        with patch.dict(sys.modules, {'radai_queue_state': queue, 'radai_atualizar': updater,
                                      'radai_watcher': watcher}):
            provider = module.build_provider(host, {'version': '8.10'},
                {'neuro_package': fixture_package(self.root),
                 'neuro_restart': lambda: (restarted.set() or {'ok': True, 'scheduled': True})})
            consent = provider.consent_policy()
            provider.accept_consent(dict(accepted=True, version=consent['version'], digest=consent['digest']))
            try:
                provider.request_plugin_update('neuro-rt', 'interromper')
                self.assertIn('overnight_interromper', events)
                self.assertFalse(state['turno_agendado'] or state['overnight'])
                if active_child:
                    self.assertIn('cancel_neuro', events)
                    self.assertEqual(owner['dono'], 'neuro')
                    self.assertTrue(held[0])
                    self.assertFalse(restarted.is_set())
                    self.assertEqual(provider.status()['state'], 'waiting')
                    owner['dono'] = None  # Host confirms its children have exited.
                self.assertTrue(restarted.wait(15), provider.status())
                deadline = time.monotonic() + 2
                while provider.status()['state'] != 'restarting' and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertEqual(provider.status()['state'], 'restarting')
            finally:
                state.update(turno_agendado=False, overnight=False)
                owner['dono'] = None
                restarted.wait(15)
                for worker in threading.enumerate():
                    if worker.name == 'neuro-update':
                        worker.join(15)
                        self.assertFalse(worker.is_alive(), 'Installer worker must finish before fixture cleanup')

    def test_scheduled_and_between_job_overnight_use_owner_api_source_and_generated(self):
        for module in (self.source, self.generated):
            for flag in ('turno_agendado', 'overnight'):
                with self.subTest(provider=module.__name__, flag=flag):
                    self.scenario(module, flag)

    def test_turn_interrupt_keeps_child_lease_until_host_confirmation(self):
        for module in (self.source, self.generated):
            with self.subTest(provider=module.__name__):
                self.scenario(module, 'turno_agendado', active_child=True)

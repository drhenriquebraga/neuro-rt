"""Host bootstrap provider. Generated host copy embeds only pinned stdlib sources."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import threading
import types

_BOOTSTRAP_LOCK = threading.Lock()


def _load_private_installer():
    with _BOOTSTRAP_LOCK:
        package = '_radai_neuro_bootstrap'
        if package + '.plugin_update' in sys.modules:
            return sys.modules[package + '.plugin_update']
        # SOURCES is generated from the reviewed files in the pinned host release.
        decoded = {}
        for name, (expected, encoded) in SOURCES.items():
            raw = base64.b64decode(encoded, validate=True)
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('Bootstrap NeuroRT não corresponde à fonte fixada no host.')
            decoded[name] = raw
        parent = types.ModuleType(package)
        parent.__path__ = []
        sys.modules[package] = parent
        try:
            for name in ('plugin_manifest', 'model_paths', 'model_registry', 'install_state', 'plugin_update'):
                key = package + '.' + name
                module = types.ModuleType(key)
                module.__package__ = package
                module.__file__ = '<host-pinned-neuro-bootstrap/' + name + '.py>'
                sys.modules[key] = module
                exec(compile(decoded[name], module.__file__, 'exec'), module.__dict__)
                setattr(parent, name, module)
        except BaseException:
            for key in list(sys.modules):
                if key == package or key.startswith(package + '.'):
                    sys.modules.pop(key, None)
            raise
        return sys.modules[package + '.plugin_update']


def build_provider(suite_root, host_info, cfg):
    root = Path(suite_root)
    held = False
    coordinator = None
    coordinator_lock = threading.Lock()
    def busy():
        import radai_queue_state as queue
        import radai_atualizar as updater
        if updater.etapa() in updater.EM_ANDAMENTO:
            return True
        return bool(queue.quem_tem_a_vez().get('dono') or updater.o_que_segura(updater._status()))
    def hold(value):
        nonlocal held
        import radai_queue_state as queue
        if value and not held and queue.fechando_ao_fim():
            raise ValueError('A fila já aguarda outra atualização ou encerramento.')
        if not value and not held:
            return
        queue.pedir_fechar_ao_fim(value)
        held = bool(value)
    def cancel():
        import radai_queue_state as queue
        import radai_atualizar as updater
        owner = queue.quem_tem_a_vez().get('dono')
        status = updater._status()
        turn_open = bool(status.get('turno_agendado') or status.get('overnight'))
        if turn_open:
            import radai_watcher
            radai_watcher.overnight_interromper()
        if owner == 'neuro':
            queue.cancelar_neuro_ativo()
        elif owner == 'lote' or (isinstance(status.get('ocupado'), dict) and status['ocupado'].get('quem') == 'lote'):
            import radai_batch
            radai_batch.cancelar()
        elif not turn_open and (owner == 'vigia' or status.get('current') or status.get('ocupado')):
            import radai_watcher
            radai_watcher.cancelar_serie_do_vigia(pausar=True)
    def get_coordinator():
        nonlocal coordinator
        with coordinator_lock:
            if coordinator is None:
                update = _load_private_installer()
                coordinator = update.UpdateCoordinator(root, host_version=host_info['version'],
                    hold=hold, busy=busy, cancel=cancel, restart=cfg.get('recarregar'),
                    client=cfg.get('neuro_release_client'), package=cfg.get('neuro_package'))
            return coordinator
    class Provider:
        def check_plugin_release(self, plugin_id, installed_version):
            return get_coordinator().client.check_plugin_release(plugin_id, installed_version)
        def request_plugin_update(self, plugin_id, action):
            return get_coordinator().request_plugin_update(plugin_id, action)
        def install(self):
            return get_coordinator().request_plugin_update('neuro-rt', 'comecar')
        def status(self):
            return get_coordinator().status()
    return Provider()

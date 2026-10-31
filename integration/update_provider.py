"""Host bootstrap provider. Generated host copy embeds only pinned stdlib sources."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
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
            for name in ('plugin_consent', 'plugin_manifest', 'model_paths', 'model_registry', 'install_state',
                         'resource_paths', 'resource_preparation', 'external_install', 'plugin_update'):
                key = package + '.' + name
                module = types.ModuleType(key)
                module.__package__ = package
                module.__file__ = '<host-pinned-neuro-bootstrap/' + name + '.py>'
                sys.modules[key] = module
                exec(compile(decoded[name], module.__file__, 'exec'), module.__dict__)
                setattr(parent, name, module)
            parent.external_install.TRUSTED_CODE_INVENTORIES = frozenset(
                globals().get('TRUSTED_CODE_INVENTORIES', ()))
        except BaseException:
            for key in list(sys.modules):
                if key == package or key.startswith(package + '.'):
                    sys.modules.pop(key, None)
            raise
        return sys.modules[package + '.plugin_update']


def inspect_local_source(folder):
    return _load_private_installer().inspect_local_source(folder)


def prepare_external_plan(payload, *, source_folder=None):
    return _load_private_installer().prepare_external_plan(payload, source_folder=source_folder)


def run_external(plan, progress, *, suite_root, host_python):
    return _load_private_installer().run_external(plan, progress, suite_root=suite_root, host_python=host_python)


def build_provider(suite_root, host_info, cfg):
    root = Path(suite_root)
    held = False
    coordinator = None
    coordinator_lock = threading.Lock()
    external_lock = threading.RLock()
    external_worker = None
    external_status = {'state': 'idle', 'reason': ''}

    def set_external_status(**values):
        with external_lock:
            external_status.update(values)
            result = dict(external_status)
        installer = _load_private_installer().install_state
        installer._atomic_json(installer._path(root, 'Plugins/NEURO RT/external-status.json'), result)
        return result
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
                    hold=hold, busy=busy, cancel=cancel, restart=cfg.get('neuro_restart'),
                    client=cfg.get('neuro_release_client'), package=cfg.get('neuro_package'),
                    host_python=host_info.get('python_executable'))
            return coordinator
    def consent():
        _load_private_installer()
        return sys.modules['_radai_neuro_bootstrap.plugin_consent']
    def require_consent():
        document = consent()
        if not document.accepted(document.config_for_suite(root), 'installation'):
            raise ValueError('Leia e aceite o termo atual do plugin antes de instalar ou atualizar o NEURO RT.')

    def external_request(plugin_id, action, plan):
        nonlocal external_worker
        update = _load_private_installer()
        with external_lock:
            if external_status['state'] == 'restarting':
                return dict(external_status)  # Scheduled lifecycle remains host-owned until this process exits.
            if external_worker is not None and external_worker.is_alive():
                return dict(external_status)
            if action == 'comecar' and busy():
                return set_external_status(state='busy', stage='waiting',
                    reason='A atualização pode esperar terminar, ou interromper agora.')
            if plan is None:
                installer = update.install_state
                state_file = installer._path(root, 'Plugins/NEURO RT/installation.json')
                state = installer._read_json(state_file) if state_file.exists() else {}
                release = get_coordinator().client.check_plugin_release(plugin_id, state.get('active_version'))
                operation = 'update' if state.get('active_version') else 'install'
                plan = update.prepare_external_plan({'mode': 'online', 'release': release, 'action': operation})
            else:
                plan = json.loads(json.dumps(plan))
                update._validate_external_plan(plan)
            if action == 'interromper':
                plan['action'] = 'interrupt_then_update'
            update._validate_external_plan(plan)
            hold(True)
            try:
                if action == 'interromper':
                    cancel()
                set_external_status(state='waiting' if busy() else 'preparing', stage='waiting' if busy() else 'handoff',
                    version=plan['version'], transaction_id=plan['transaction_id'], reason='', error_code='', error_stage='')
            except BaseException:
                hold(False)
                raise

            def handoff():
                try:
                    while busy():
                        time.sleep(.1)
                    result = cfg['neuro_external_install'](plan)
                    if (not isinstance(result, dict) or result.get('ok') is not True
                            or result.get('scheduled') is not True):
                        raise ValueError('A suíte não confirmou a manutenção externa.')
                except BaseException as error:
                    hold(False)
                    diagnostic = update.install_state.sanitize_install_error(error, 'preparing')
                    set_external_status(state='failed', **diagnostic)
                    return
                # A positive scheduled ACK transfers lifecycle ownership. A late
                # progress write cannot revoke it or release the host reservation.
                try:
                    set_external_status(state='restarting', stage='handoff',
                        reason='A manutenção externa foi solicitada. Aguardando a reabertura da suíte.')
                except (OSError, ValueError):
                    pass
            external_worker = threading.Thread(target=handoff, name='neuro-external-handoff', daemon=True)
            external_worker.start()
            return dict(external_status)
    class Provider:
        def consent_policy(self):
            return consent().policy()
        def consent_status(self):
            document = consent()
            config = document.config_for_suite(root)
            return {'installation_accepted': document.accepted(config, 'installation'),
                    'first_use_accepted': document.accepted(config, 'first_use')}
        def accept_consent(self, payload):
            document = consent()
            return document.accept(document.config_for_suite(root), 'installation', payload)
        def check_plugin_release(self, plugin_id, installed_version):
            return get_coordinator().client.check_plugin_release(plugin_id, installed_version)
        def refresh_plugin_release(self, plugin_id, installed_version):
            return get_coordinator().client.refresh_plugin_release(plugin_id, installed_version)
        def inspect_local_source(self, folder):
            return inspect_local_source(folder)
        def prepare_external_plan(self, payload, *, source_folder=None):
            require_consent()
            return prepare_external_plan(payload, source_folder=source_folder)
        def request_plugin_update(self, plugin_id, action, plan=None):
            # All entry paths are guarded before queue hold, cancellation or I/O.
            require_consent()
            if plugin_id != 'neuro-rt' or action not in ('comecar', 'esperar', 'interromper'):
                raise ValueError('Ação de atualização inválida.')
            if callable(cfg.get('neuro_external_install')):
                return external_request(plugin_id, action, plan)
            if plan is not None:
                raise ValueError('Atualize a suíte para usar manutenção externa e fonte local.')
            return get_coordinator().request_plugin_update(plugin_id, action)
        def install(self):
            return self.request_plugin_update('neuro-rt', 'comecar')
        def status(self):
            if callable(cfg.get('neuro_external_install')):
                with external_lock:
                    if external_status['state'] != 'idle':
                        return dict(external_status)
                installer = _load_private_installer().install_state
                path = installer._path(root, 'Plugins/NEURO RT/external-status.json')
                if path.exists():
                    return installer._read_json(path)
                return dict(external_status)
            return get_coordinator().status()
    return Provider()

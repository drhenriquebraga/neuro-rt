"""Narrow, dependency-free host contract. Callbacks keep their original owners."""
from dataclasses import dataclass, field
from types import MappingProxyType


class HostDependencyUnavailable(RuntimeError):
    pass


def _missing(name):
    def unavailable(*args, **kwargs):
        raise HostDependencyUnavailable('Serviço compartilhado indisponível: ' + name)
    return unavailable


@dataclass(frozen=True)
class HostServices:
    host_info: dict
    resolve_series_ticket: object
    queue_bridge: object
    device_preference: object
    register_result: object
    export_rtstruct: object
    viewer_routes: object
    missing_dependencies: tuple = field(default_factory=tuple)

    def require(self, *names):
        missing = [name for name in names if name in self.missing_dependencies]
        if missing:
            raise HostDependencyUnavailable('Serviços compartilhados indisponíveis: ' + ', '.join(missing))


def build_host_services(host_info, bindings=None, *, queue_bridge_factory=None):
    """Bindings are internal composition callbacks, never workstation settings.

    Missing services reject use explicitly; this factory creates no importer,
    image writer, result store, queue or alternate device selector.
    """
    bindings = dict(bindings or {})
    missing = []
    callbacks = {}
    for name in ('resolve_series_ticket', 'register_result', 'export_rtstruct'):
        callback = bindings.get(name)
        if not callable(callback):
            missing.append(name)
            callback = _missing(name)
        callbacks[name] = callback
    queue = bindings.get('queue_bridge')
    if queue is None and queue_bridge_factory is not None:
        queue = queue_bridge_factory()
    if queue is None:
        missing.append('queue_bridge')
    preference = bindings.get('device_preference', lambda: 'auto')
    if not callable(preference):
        raise TypeError('device_preference deve ser uma função do host.')

    def device_preference():
        value = preference()
        if value not in ('auto', 'cpu', 'cuda'):
            raise ValueError('Preferência global de processamento inválida.')
        return value

    viewers = bindings.get('viewer_routes')
    if viewers is None:
        missing.append('viewer_routes')
        viewers = MappingProxyType({})
    return HostServices(MappingProxyType(dict(host_info)), queue_bridge=queue,
                        device_preference=device_preference, viewer_routes=viewers,
                        missing_dependencies=tuple(missing), **callbacks)

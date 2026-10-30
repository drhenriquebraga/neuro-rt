"""Pure path resolution for the versioned installation; does not create files.

``installation_state`` is None or a mapping with ``state``, ``active_version``
and optional ``runtime={id, lock_digest, python}``. ``python`` is relative to
that runtime directory and defaults to ``python.exe`` on the Windows target.
With ``execution_mode='host'``, runtime must be None and the caller supplies the
trusted host_python binding; installed metadata never selects an interpreter.
Runtime selection/integrity and transactional state publication belong to I02.
"""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping

from .plugin_manifest import _numeric_version, _relative_path, validate_host_runtime


class InstallationState(str, Enum):
    ABSENT = 'absent'
    CHECKING = 'checking'
    INSTALLING = 'installing'
    INSTALLED_PENDING_RESTART = 'installed_pending_restart'
    READY = 'ready'
    UPDATING = 'updating'
    INCOMPATIBLE = 'incompatible'
    FAILED = 'failed'


@dataclass(frozen=True)
class PluginPaths:
    host_root: Path
    plugin_root: Path
    active_version: str | None
    code_dir: Path | None
    runtimes_dir: Path
    runtime_dir: Path | None
    worker_python: Path | None
    models_dir: Path
    data_dir: Path
    config_dir: Path
    staging_dir: Path
    installation_file: Path
    state: InstallationState
    execution_mode: str = 'isolated'


def resolve_plugin_paths(host_root, installation_state, *, host_python=None) -> PluginPaths:
    host_root = Path(host_root).resolve()
    if installation_state is None:
        installation_state = {'state': 'absent'}
    if not isinstance(installation_state, Mapping):
        raise ValueError('Estado da instalação deve ser um objeto.')
    try:
        state = InstallationState(installation_state.get('state'))
    except (ValueError, TypeError) as error:
        raise ValueError('Estado público da instalação inválido.') from error
    plugin_root = _relative_path(host_root, 'Plugins/NEURO RT')
    versions_dir = _relative_path(plugin_root, 'versions')
    runtimes_dir = _relative_path(plugin_root, 'runtimes')
    active_version = installation_state.get('active_version')
    code_dir = None
    if active_version is not None:
        _numeric_version(active_version)
        code_dir = _relative_path(versions_dir, active_version)
    runtime_dir = worker_python = None
    runtime = installation_state.get('runtime')
    execution_mode = installation_state.get('execution_mode', 'isolated')
    if execution_mode not in ('isolated', 'host'):
        raise ValueError('Modo de execução da instalação inválido.')
    if execution_mode == 'host':
        if runtime is not None or any(key in installation_state for key in ('host_python', 'python_executable', 'worker_python')):
            raise ValueError('O estado instalado não pode fornecer um Python ou runtime privado.')
        worker_python = validate_host_runtime(host_python)
    elif runtime is not None:
        if not isinstance(runtime, Mapping):
            raise ValueError('Runtime da instalação inválido.')
        runtime_id, digest = runtime.get('id'), runtime.get('lock_digest')
        if not isinstance(runtime_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', runtime_id):
            raise ValueError('Identificador de runtime inválido.')
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('Digest do lock de runtime deve ser SHA-256 hexadecimal minúsculo.')
        runtime_dir = _relative_path(runtimes_dir, f'{runtime_id}/{digest}')
        worker_python = _relative_path(runtime_dir, runtime.get('python', 'python.exe'))
    return PluginPaths(
        host_root=host_root, plugin_root=plugin_root, active_version=active_version,
        code_dir=code_dir, runtimes_dir=runtimes_dir, runtime_dir=runtime_dir,
        worker_python=worker_python, models_dir=_relative_path(plugin_root, 'models'),
        data_dir=_relative_path(plugin_root, 'data'), config_dir=_relative_path(plugin_root, 'config'),
        staging_dir=_relative_path(plugin_root, 'staging'),
        installation_file=_relative_path(plugin_root, 'installation.json'), state=state,
        execution_mode=execution_mode)

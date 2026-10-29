"""Lightweight, local plugin metadata; never imports an inference engine.

``host_min_version=None`` identifies an unpublished compatibility requirement.
Such a draft may be inspected but must not be mounted in a production host.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Mapping


MANIFEST_SCHEMA = 'neuro-rt/plugin-manifest/1'
HOST_CONTRACT = 'local-suite/plugins/1'
PLUGIN_ID = 'neuro-rt'


def _numeric_version(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)*', value):
        raise ValueError('A versão deve ser uma string numérica, por exemplo 2.10.0.')
    return tuple(int(part) for part in value.split('.'))


def _relative_path(root, value):
    """Resolve a portable relative reference, rejecting Windows aliases too."""
    if not isinstance(value, str) or not value:
        raise ValueError('Referência relativa ausente ou inválida.')
    windows = PureWindowsPath(value)
    parts = value.replace('\\', '/').split('/')
    if (windows.drive or windows.root or value.startswith('/') or
            any(part in ('', '.', '..') or part.endswith((' ', '.')) for part in parts) or
            any(ord(char) < 32 or char in '<>:"|?*' for char in value)):
        raise ValueError('Referência deve ser relativa e permanecer dentro da instalação.')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {
        f'{prefix}{number}' for prefix in ('COM', 'LPT') for number in range(1, 10)}
    if any(part.split('.')[0].upper() in reserved for part in parts):
        raise ValueError('Referência contém nome reservado do Windows.')
    root = Path(root).resolve()
    resolved = root.joinpath(*parts).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('Referência escapa da instalação, inclusive por link simbólico.')
    return resolved


@dataclass(frozen=True)
class PluginManifest:
    schema: str
    id: str
    version: str
    host_contract: str
    host_min_version: str | None
    entrypoint: str
    adapter: str
    catalog: str
    runtimes: dict
    artifacts: tuple


@dataclass(frozen=True)
class CompatibilityResult:
    compatible: bool
    required_contract: str
    required_host_version: str | None
    reason: str


def read_manifest(path) -> PluginManifest:
    """Read and validate metadata only; referenced files may await installation."""
    path = Path(path)
    try:
        values = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f'Não foi possível ler o manifesto do plugin: {error}') from error
    if not isinstance(values, dict):
        raise ValueError('O manifesto deve ser um objeto JSON.')
    for key, expected in (('schema', MANIFEST_SCHEMA), ('id', PLUGIN_ID),
                          ('host_contract', HOST_CONTRACT)):
        if values.get(key) != expected:
            raise ValueError(f'Manifesto com {key} inválido; esperado {expected}.')
    _numeric_version(values.get('version'))
    if 'host_min_version' not in values:
        raise ValueError('Manifesto sem host_min_version; use null até publicar o requisito.')
    minimum = values['host_min_version']
    if minimum is not None:
        _numeric_version(minimum)
    # The public entrypoint is a route, whereas adapter/catalog are file references.
    if values.get('entrypoint') != '/neuro/':
        raise ValueError('Entrada do plugin deve ser a rota /neuro/.')
    adapter = values.get('adapter')
    if not isinstance(adapter, str) or adapter.count(':') != 1:
        raise ValueError('Adaptador deve declarar arquivo relativo e função.')
    adapter_path, function = adapter.split(':')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', function):
        raise ValueError('Função do adaptador inválida.')
    _relative_path(path.parent, adapter_path)
    _relative_path(path.parent, values.get('catalog'))
    runtimes = values.get('runtimes')
    if not isinstance(runtimes, dict) or not runtimes:
        raise ValueError('Manifesto deve declarar os runtimes do plugin.')
    for runtime_id, runtime in runtimes.items():
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', runtime_id):
            raise ValueError('Identificador de runtime inválido.')
        if not isinstance(runtime, dict):
            raise ValueError('Descrição do runtime inválida.')
        _relative_path(path.parent, runtime.get('python'))
    artifacts = values.get('artifacts')
    if not isinstance(artifacts, list):
        raise ValueError('Manifesto deve declarar uma lista de artefatos.')
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError('Descrição de artefato inválida.')
        _relative_path(path.parent, artifact.get('path'))
    return PluginManifest(
        schema=values['schema'], id=values['id'], version=values['version'],
        host_contract=values['host_contract'], host_min_version=minimum,
        entrypoint=values['entrypoint'], adapter=adapter, catalog=values['catalog'],
        runtimes=runtimes, artifacts=tuple(artifacts))


def check_host_compatibility(manifest, host_info) -> CompatibilityResult:
    """Host info is a mapping with ``contract`` and its actual ``version``."""
    def result(compatible, reason):
        return CompatibilityResult(compatible, manifest.host_contract,
                                   manifest.host_min_version, reason)

    if not isinstance(host_info, Mapping) or host_info.get('contract') != manifest.host_contract:
        return result(False, f'Host deve oferecer o contrato {manifest.host_contract}.')
    if manifest.host_min_version is None:
        return result(False, 'Versão mínima do host ainda não publicada no manifesto.')
    try:
        actual = _numeric_version(host_info.get('version'))
        minimum = _numeric_version(manifest.host_min_version)
    except ValueError:
        return result(False, 'Versão do host ausente ou inválida; compatibilidade não confirmada.')
    width = max(len(actual), len(minimum))
    if actual + (0,) * (width - len(actual)) < minimum + (0,) * (width - len(minimum)):
        return result(False, f'Host requer atualização para {manifest.host_min_version} ou posterior.')
    return result(True, 'Host compatível com o contrato e a versão mínima do plugin.')

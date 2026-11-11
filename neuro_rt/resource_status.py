"""Read installed weight availability separately from the active code version."""
import hashlib
import json
import re

from .install_state import _path, _plain, _read_json
from .resource_paths import resolve_resources


def inspect_weights(plugin_root, code_dir, installation):
    recipe = _read_json(_path(code_dir, 'catalog/resource_recipe.json'))
    canonical = (json.dumps(recipe, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode()
    version = installation.get('resource_bundle_version')
    if not isinstance(version, str) or not re.fullmatch(r'\d+(?:\.\d+){1,3}', version):
        version = None
    missing, present = [], False
    for model in recipe.get('models', []):
        relative = 'models/' + model['id'] + '/' + model['revision']
        complete = True
        for name, record in model['files'].items():
            try:
                file = _path(plugin_root, relative + '/' + name)
                valid = file.is_file() and file.stat().st_size == record['size']
                present |= file.is_file()
            except (OSError, ValueError):
                valid = False
            complete &= valid
        if not complete:
            missing.append(model['id'])
    descriptor = installation.get('resources')
    try:
        descriptor, extras, receipt_file = resolve_resources(plugin_root, code_dir, descriptor)
        if descriptor is None:
            raise ValueError('Recursos ainda não preparados.')
        receipt = _read_json(receipt_file)
        for name, record in receipt.get('extra_file_inventory', {}).items():
            file = _path(extras, name)
            if not file.is_file() or file.stat().st_size != record['size']:
                raise ValueError('Complemento ausente.')
        for adapter, value in descriptor['capabilities'].items():
            if not value['available']:
                missing.append('adapter:' + adapter)
        present = True
    except (OSError, ValueError, KeyError, TypeError):
        missing.append('extras')
    return {'state': ('partial' if present else 'missing') if missing else 'ready',
            'version': version, 'recipe_sha256': hashlib.sha256(canonical).hexdigest(),
            'missing_components': sorted(set(missing))}


def installed_weights(plugin_paths):
    if plugin_paths is None or plugin_paths.code_dir is None:
        return {'state': 'missing', 'version': None, 'recipe_sha256': None,
                'missing_components': ['extras']}
    try:
        installation = _read_json(_plain(plugin_paths.installation_file))
        if installation.get('active_version') != plugin_paths.active_version:
            return {'state': 'checking', 'version': None, 'recipe_sha256': None,
                    'missing_components': []}
        return inspect_weights(plugin_paths.plugin_root, plugin_paths.code_dir, installation)
    except (OSError, ValueError, KeyError, TypeError):
        return {'state': 'partial', 'version': None, 'recipe_sha256': None,
                'missing_components': ['extras']}

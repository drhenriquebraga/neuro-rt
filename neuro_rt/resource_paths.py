"""Validate the installed delta descriptor without loading a scientific engine."""
import hashlib
import json
from pathlib import Path
import re
from collections.abc import Mapping

FIELDS = {'schema', 'recipe_digest', 'extras_digest', 'extras_relative_path',
          'receipt_relative_path', 'receipt_sha256', 'model_relative_paths', 'capabilities'}

def _sha(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Hash do recurso inválido.')
    return value

def _read(path):
    if path.stat().st_size > 3 * 1024 * 1024:
        raise ValueError('Descrição dos recursos excede o limite.')
    raw = path.read_bytes()
    value = json.loads(raw.decode('utf-8'))
    if not isinstance(value, dict): raise ValueError('Descrição dos recursos inválida.')
    return value, raw

def resolve_resources(plugin_root, code_dir, descriptor):
    """Return (copied descriptor, extras_dir, receipt_file), all confined and hashed."""
    if descriptor is None:
        return None, None, None
    from .install_state import _path, _plain
    try:
        if (code_dir is None or not isinstance(descriptor, Mapping)
                or set(descriptor) != FIELDS or descriptor.get('schema') != 'neuro-rt/resolved-resources/1'):
            raise ValueError('Recursos instalados inválidos.')
        _plain(plugin_root)
        recipe_digest, extras_digest = _sha(descriptor['recipe_digest']), _sha(descriptor['extras_digest'])
        if descriptor['extras_relative_path'] != 'extras/' + extras_digest + '/site-packages':
            raise ValueError('Pasta de extras deve corresponder ao inventário verificado.')
        if descriptor['receipt_relative_path'] != 'resources/' + recipe_digest + '.json':
            raise ValueError('Recibo deve corresponder à receita verificada.')
        recipe, _ = _read(_path(code_dir, 'catalog/resource_recipe.json'))
        canonical = (json.dumps(recipe, sort_keys=True, separators=(',', ':'), ensure_ascii=True)+'\n').encode()
        if hashlib.sha256(canonical).hexdigest() != recipe_digest:
            raise ValueError('A receita dos recursos difere do código ativo.')
        receipt_file = _path(plugin_root, descriptor['receipt_relative_path'])
        receipt, raw = _read(receipt_file)
        if hashlib.sha256(raw).hexdigest() != _sha(descriptor['receipt_sha256']):
            raise ValueError('Recibo de recursos foi alterado ou está incompleto.')
        for key in FIELDS - {'receipt_relative_path', 'receipt_sha256'}:
            if receipt.get(key) != descriptor[key]:
                raise ValueError('Estado e recibo de recursos não correspondem.')
        catalog, _ = _read(_path(code_dir, 'catalog/models.json'))
        expected = {}
        def add(spec):
            if not isinstance(spec, dict): raise ValueError('Modelo de recursos inválido.')
            if spec.get('host_managed') is True:
                return  # Buti and its weights already belong to the complete suite.
            if spec.get('catalog_state') == 'distributed':
                ident, revision = spec.get('id'), spec.get('revision')
                if not all(isinstance(v, str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', v) for v in (ident, revision)):
                    raise ValueError('Identidade dos recursos inválida.')
                relative = 'models/' + ident + '/' + revision
                if ident in expected and expected[ident] != relative:
                    raise ValueError('Revisões de um recurso não correspondem.')
                expected[ident] = relative
            for dependency in spec.get('dependencies', []): add(dependency)
        for spec in catalog.get('models', []): add(spec)
        if descriptor['model_relative_paths'] != expected:
            raise ValueError('Pastas dos modelos não correspondem ao catálogo ativo.')
        for relative in expected.values():
            if not _path(plugin_root, relative).is_dir():
                raise ValueError('Modelo verificado ausente.')
        extras_dir = _path(plugin_root, descriptor['extras_relative_path'])
        if not extras_dir.is_dir(): raise ValueError('Extras verificados ausentes.')
        capabilities = descriptor['capabilities']
        if not isinstance(capabilities, dict) or any(
            not isinstance(k, str) or not re.fullmatch('[A-Za-z0-9_.-]{1,80}', k)
            or not isinstance(v, dict) or type(v.get('available')) is not bool
            or not isinstance(v.get('reason'), str) for k,v in capabilities.items()):
            raise ValueError('Capacidades dos recursos inválidas.')
        return json.loads(json.dumps(dict(descriptor))), extras_dir, receipt_file
    except (OSError, UnicodeError, KeyError, TypeError, RecursionError) as error:
        raise ValueError('Recursos instalados ausentes ou inválidos; prepare novamente o plugin.') from error

"""Resolve imports through the host's own component discovery in source layouts."""
import importlib.util
import sys
import re
from pathlib import Path


def host_module_path(host_app, module_name):
    if not isinstance(module_name, str) or not re.fullmatch(r'[A-Za-z_]\w*', module_name):
        raise ValueError('Nome de módulo do host inválido.')
    app = Path(host_app).resolve()
    suite = app.parent if app.name.lower() == 'app' else app
    resolver = suite / 'tools/_componentes.py'
    if resolver.is_file():
        spec = importlib.util.spec_from_file_location('_neuro_host_componentes', resolver)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        matches = module.arquivos('app', padrao=module_name + '.py', suite=str(suite))
        if len(matches) == 1 and Path(matches[0]).is_file():
            return Path(matches[0]).resolve()
        return None
    direct = app / (module_name + '.py')
    return direct if direct.is_file() else None


def prepare_host_imports(host_app):
    app = Path(host_app).resolve()
    if not app.is_dir():
        raise ValueError('Pasta de módulos do Local Suite indisponível.')
    suite = app.parent if app.name.lower() == 'app' else app
    source_app = suite / 'app'
    resolver = suite / 'tools' / '_componentes.py'
    if resolver.is_file():
        spec = importlib.util.spec_from_file_location('_neuro_host_componentes', resolver)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.ligar_caminho(str(suite))
        if source_app.is_dir() and str(source_app) not in sys.path:
            sys.path.insert(0, str(source_app))
    if str(app) not in sys.path:
        sys.path.insert(0, str(app))
    return app

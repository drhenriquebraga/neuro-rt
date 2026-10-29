"""Monta a tela Nidus uma vez, usando os serviços e a origem do host."""
from pathlib import Path
import sys


def montar(app, host_services):
    receipt = getattr(app.state, 'neuro_nidus', None)
    if receipt is not None:
        return receipt
    root = Path(__file__).resolve().parent.parent
    suite = Path(host_services.host_info['suite_root']).resolve()
    resolver = suite / 'tools/_componentes.py'
    if resolver.is_file():
        sys.path.insert(0, str(resolver.parent))
        import _componentes
        _componentes.ligar_caminho(str(suite), extras=(str(root / 'app'),))
    else:
        from integration.host_imports import prepare_host_imports
        prepare_host_imports(suite)
        if str(root / 'app') not in sys.path:
            sys.path.insert(0, str(root / 'app'))
    loaded = sys.modules.get('radai_nidus_screen')
    if loaded is not None and Path(loaded.__file__).resolve().parent != root / 'app':
        raise RuntimeError('A tela Nidus já foi carregada fora do plugin Neuro RT.')
    import radai_projection
    core = sys.modules.get('radai_nidus')
    if core is not None and core is not radai_projection:
        raise RuntimeError('O core Nidus já foi carregado fora do plugin Neuro RT.')
    import radai_nidus_screen
    radai_nidus_screen.montar(app)
    receipt = {'screen': radai_nidus_screen, 'path': '/nidus/projecao'}
    app.state.neuro_nidus = receipt
    return receipt

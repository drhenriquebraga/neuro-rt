import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SUITE = Path(os.environ.get('NEURO_HOST_ROOT', ROOT.parent / 'AUTO_CONTORNO'))


class NidusMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (SUITE / 'tools/_componentes.py').is_file():
            raise unittest.SkipTest('Integração Nidus requer checkout do host; configure NEURO_HOST_ROOT.')
        sys.path.insert(0, str(SUITE / 'tools'))
        import _componentes
        cls.components = _componentes

    def test_archived_nidus_is_not_a_base_component(self):
        self.assertNotIn('NIDUS_RT', [d['nome'] for _, d in self.components.componentes(str(SUITE))])
        lock = json.loads((SUITE / 'build/componentes.lock.json').read_text(encoding='utf-8'))
        self.assertNotIn('NIDUS_RT', [d['nome'] for d in lock['componentes']])

    def test_base_mount_excludes_archived_nidus_even_with_manifest(self):
        with tempfile.TemporaryDirectory(prefix='neuro_nidus_base_') as tmp:
            base = Path(tmp)
            suite = base / 'SUITE'
            (suite / 'app').mkdir(parents=True)
            (suite / 'app/radai_ui.py').write_text('X = 1\n')
            for name in ('NIDUS_RT', 'RECON_3D'):
                (base / name / 'app').mkdir(parents=True)
                (base / name / 'componente.json').write_text(json.dumps({'suite': 'local-suite', 'nome': name}))
                (base / name / 'app' / ('radai_' + name.lower() + '.py')).write_text('X = 1\n')
            mounted = self.components.montar_app(str(base / 'output'), str(suite))
            self.assertIn('radai_recon_3d.py', mounted)
            self.assertNotIn('radai_nidus_rt.py', mounted)
            plugin = base / 'NEURO_RT/app'
            plugin.mkdir(parents=True)
            (plugin / 'radai_nidus_screen.py').write_text('X = 1\n')
            self.components.ligar_caminho(str(suite), extras=(str(plugin),))
            mounted = self.components.montar_app(str(base / 'output2'), str(suite))
            self.assertNotIn('radai_nidus_screen.py', mounted)

    def test_recon_pages_do_not_import_nidus_or_scientific_modules(self):
        program = '''
import sys
sys.path.insert(0, sys.argv[1] + '/tools')
import _componentes
_componentes.ligar_caminho(sys.argv[1])
import radai_recon3d_screen as screen
import radai_recon3d_vascular as vascular
assert 'function radaiIncidencia(' in screen.pagina('geral')
assert vascular.AJUDA
assert not {'radai_nidus', 'radai_nidus_screen', 'numpy', 'SimpleITK'} & set(sys.modules)
'''
        result = subprocess.run([sys.executable, '-c', program, str(SUITE)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_installer_collector_excludes_the_archived_component(self):
        spec = importlib.util.spec_from_file_location('u05_installer', SUITE / 'build/empacotar_instalador.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory(prefix='neuro_nidus_pack_') as tmp:
            base = Path(tmp)
            suite = base / 'SUITE'
            suite.mkdir()
            for name in ('NIDUS_RT', 'RECON_3D'):
                (base / name / 'app').mkdir(parents=True)
                (base / name / 'componente.json').write_text(json.dumps({'suite': 'local-suite', 'nome': name}))
                (base / name / 'app' / ('radai_' + name.lower() + '.py')).write_text('X = 1\n')
            for helper in ('radai_projection.py', 'radai_projection_bone.py'):
                (base / 'RECON_3D/app' / helper).write_text('X = 1\n')
            lock = base / 'lock.json'
            lock.write_text(json.dumps({'componentes': [{'nome': 'RECON_3D', 'repositorio': 'test/recon', 'tag': 'v8.9'}]}))
            with patch.object(installer, 'conferir_versionados'):
                collected = dict(installer.coletar_componentes(set(), suite=suite, trava=lock))
            self.assertIn('app/radai_recon_3d.py', collected)
            self.assertNotIn('app/radai_nidus_rt.py', collected)

    def test_nidus_alias_uses_the_same_core_object(self):
        self.components.ligar_caminho(str(SUITE), extras=(str(ROOT / 'app'),))
        import radai_nidus
        import radai_projection
        self.assertIs(radai_nidus, radai_projection)
        import radai_nidus_screen
        import radai_projection_bone
        self.assertIs(radai_nidus_screen.osso_da_segmentacao, radai_projection_bone.osso_da_segmentacao)

    @unittest.skipUnless(importlib.util.find_spec('fastapi') is not None,
                         'A montagem HTTP requer FastAPI no Python do host.')
    def test_bridge_mounts_routes_once(self):
        from fastapi import FastAPI
        from integration.nidus_bridge import montar
        app = FastAPI()
        host = SimpleNamespace(host_info={'suite_root': str(SUITE)})
        first = montar(app, host)
        routes = [(r.path, tuple(sorted(r.methods or ()))) for r in app.routes]
        self.assertIs(first, montar(app, host))
        self.assertEqual(routes, [(r.path, tuple(sorted(r.methods or ()))) for r in app.routes])
        self.assertEqual(1, len([r for r in app.routes if r.path == '/nidus/projecao']))
        import radai_nidus_screen
        radai_nidus_screen.montar(app)
        self.assertEqual(1, len([r for r in app.routes if r.path == '/nidus/projecao']))


if __name__ == '__main__':
    unittest.main()

"""Compose the real host screen and exercise its browser contract synthetically."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'neuro_rt.local.json').read_text()) if (ROOT/'neuro_rt.local.json').is_file() else {}
PLAYWRIGHT = os.environ.get('NEURO_PLAYWRIGHT_MODULE',r'playwright')
CHROME = os.environ.get('NEURO_BROWSER_EXECUTABLE',r'C:/Program Files/Google/Chrome/Application/chrome.exe')
HOST_APP = os.environ.get('NEURO_HOST_APP', CONFIG.get('host_app') or '')
STUDY_HOST_PYTHON = os.environ.get('NEURO_STUDY_HOST_PYTHON', CONFIG.get('host_python') or '')
TEMP_ROOT = ROOT/'runtime/test-tmp'
TEMP_ROOT.mkdir(parents=True,exist_ok=True)


class NativeStudyScreenTests(unittest.TestCase):
    def test_anatomy_display_name_preserves_existing_consent(self):
        from integration.testing_access import policy
        from neuro_rt.tool_availability import available_tools

        tool = next(tool for tool in available_tools() if tool['id'] == 'anatomia')
        self.assertEqual(tool['title'], 'AutoContorno Neuro')
        self.assertEqual(tool['route'], '/neuro/anatomia')
        self.assertEqual(policy('anatomia')['digest'],
                         '9a2d82994506236f426b94ab0ec8ff432850eb81774923cec7e2fb79856d16f0')

    def test_update_translations_cover_all_host_page_languages(self):
        catalog = json.loads((ROOT/'web/plugin-update-i18n.json').read_text(encoding='utf-8'))
        languages = set(json.loads((ROOT/'web/study-i18n.json').read_text(encoding='utf-8')))
        self.assertEqual(set(catalog), languages)
        for code, phrases in catalog.items():
            self.assertEqual(set(phrases), set(catalog['pt-BR']), code)
            self.assertTrue(all(isinstance(value,str) and value.strip() for value in phrases.values()), code)

    @unittest.skipUnless(Path(STUDY_HOST_PYTHON).is_file() and HOST_APP and Path(HOST_APP).is_dir(), 'Runtime do host indisponível.')
    def test_plugin_landing_consumes_release_check_and_update_actions(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            output = Path(tmp)/'landing.html'
            code = ('import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
                    'from integration.host_imports import prepare_host_imports;prepare_host_imports(sys.argv[2]);'
                    'from integration.radai_neuro_screen import pagina_neuro;'
                    'Path(sys.argv[3]).write_text(pagina_neuro(None,{"state":"ready"}),encoding="utf-8")')
            run = subprocess.run([STUDY_HOST_PYTHON,'-c',code,str(ROOT),HOST_APP,str(output)],capture_output=True,timeout=60)
            self.assertEqual(run.returncode,0,run.stderr.decode(errors='replace')[-2000:])
            page = output.read_text(encoding='utf-8')
            self.assertTrue('id="neuro-update"' in page, 'Missing native plugin update panel')
            self.assertTrue('/api/plugins/neuro-rt/update' in page, 'Missing update action consumer')
            self.assertTrue('release_check' in page, 'Missing release check consumer')
            self.assertIn('AutoContorno Neuro', page)
            if shutil.which('node') and Path(PLAYWRIGHT).is_dir() and Path(CHROME).is_file():
                env = dict(os.environ,NEURO_UPDATE_HTML=str(output),NEURO_PLAYWRIGHT_MODULE=PLAYWRIGHT,NEURO_BROWSER_EXECUTABLE=CHROME)
                run = subprocess.run([shutil.which('node'),str(ROOT/'tests/plugin_update_ui_browser.cjs')],capture_output=True,timeout=90,env=env)
                self.assertEqual(run.returncode,0,run.stderr.decode(errors='replace')[-3000:])
                self.assertIn('PASS:',run.stdout.decode(errors='replace'))
                print(run.stdout.decode(errors='replace').strip())

    @unittest.skipUnless(Path(STUDY_HOST_PYTHON).is_file() and HOST_APP and Path(HOST_APP).is_dir(), 'Runtime do host indisponível.')
    def test_native_screen_includes_common_review_without_iframe(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            code = ('import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
                    'from integration.host_imports import prepare_host_imports;prepare_host_imports(sys.argv[2]);'
                    'from integration.radai_neuro_screen import pagina_estudo;'
                    '[Path(sys.argv[3], category + ".html").write_text(pagina_estudo(category, None), encoding="utf-8") '
                    'for category in ("glioma", "metastasis", "meningioma", "anatomia")]')
            run = subprocess.run([STUDY_HOST_PYTHON,'-c',code,str(ROOT),HOST_APP,tmp],capture_output=True,timeout=60)
            self.assertEqual(run.returncode,0,run.stderr.decode(errors='replace')[-2000:])
            for category in ('glioma', 'metastasis', 'meningioma', 'anatomia'):
                with self.subTest(category=category):
                    page = (Path(tmp) / (category + '.html')).read_text(encoding='utf-8')
                    self.assertNotIn('<iframe',page)
                    self.assertIn('radai_rev_corpo',page)
                    self.assertIn('radai-tarefas-css',page)
                    self.assertIn('function r3gLerStl',page)
                    self.assertIn('data-ui-ps-abre="nr-series-picker"', page)
                    self.assertIn('id="nr-series-picker" data-ui-ps', page)
                    self.assertIn('id="nr-picker-archive" data-ui-acervo', page)
                    self.assertIn('id="nr-picker-source-t-folder"', page)
                    self.assertIn('<header class="ui-fn">', page)
                    self.assertIn('<div class="ui-alerta esq">', page)
                    for number in range(1, 4):
                        self.assertIn(f'<span class="ps-num">{number}</span>', page)
                    self.assertIn('<footer class="nr-footer">', page)
                    self.assertIn('data-titulo="Carregar imagens"', page)
                    self.assertIn('Adicionar novas séries', page)
                    if category == 'anatomia':
                        self.assertIn('<title>AutoContorno Neuro</title>', page)
            if shutil.which('node') and Path(PLAYWRIGHT).is_dir() and Path(CHROME).is_file():
                env = dict(os.environ,NEURO_STUDY_HTML=str(Path(tmp) / 'glioma.html'),NEURO_PLAYWRIGHT_MODULE=PLAYWRIGHT,NEURO_BROWSER_EXECUTABLE=CHROME)
                run = subprocess.run([shutil.which('node'),str(ROOT/'tests/study_ui_browser.cjs')],capture_output=True,timeout=180,env=env)
                self.assertEqual(run.returncode,0,run.stderr.decode(errors='replace')[-3500:])
                self.assertIn('PASS:',run.stdout.decode(errors='replace'))
                print(run.stdout.decode(errors='replace').strip())


if __name__ == '__main__': unittest.main()

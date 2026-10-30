import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from neuro_rt.plugin_consent import policy

ROOT=Path(__file__).resolve().parents[1]
PLAYWRIGHT=os.environ.get('NEURO_PLAYWRIGHT_MODULE','C:/Users/henri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')
CHROME=os.environ.get('NEURO_BROWSER_EXECUTABLE','C:/Program Files/Google/Chrome/Application/chrome.exe')


class InstallProgressBrowserTests(unittest.TestCase):
    def test_progress_catalog_keeps_all_twelve_languages(self):
        data=json.loads((ROOT/'web/plugin-update-i18n.json').read_text(encoding='utf-8'))
        self.assertEqual(len(data),12)
        for code,phrases in data.items():
            self.assertEqual(set(phrases),set(data['pt-BR']),code)
            for text in ('Copiando os arquivos da instalação…','Pacote preparado. Aguardando reabertura da Local Suite.','Arquivos:','Etapa:','Código:'):
                self.assertTrue(phrases.get(text,'').strip(),(code,text))

    @unittest.skipUnless(shutil.which('node') and Path(PLAYWRIGHT).is_dir() and Path(CHROME).is_file(),'Chrome/Playwright indisponível.')
    def test_installation_progress_and_restart_proof(self):
        base=ROOT/'runtime/test-tmp';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            document=Path(tmp)/'policy.json';document.write_text(json.dumps(policy()),encoding='utf-8')
            env=dict(os.environ,NEURO_CONSENT_POLICY=str(document),NEURO_PLAYWRIGHT_MODULE=PLAYWRIGHT,NEURO_BROWSER_EXECUTABLE=CHROME)
            result=subprocess.run([shutil.which('node'),str(ROOT/'tests/install_progress_ui_browser.cjs')],env=env,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            print(result.stdout.strip())

    @unittest.skipUnless(shutil.which('node') and Path(PLAYWRIGHT).is_dir() and Path(CHROME).is_file(),'Chrome/Playwright indisponível.')
    def test_existing_first_install_flow_uses_current_controller(self):
        base=ROOT/'runtime/test-tmp';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            catalog=json.loads((ROOT/'web/plugin-update-i18n.json').read_text(encoding='utf-8'))
            script=(ROOT/'web/plugin-update.js').read_text(encoding='utf-8')
            html=('<html lang="pt-BR"><body><section id="neuro-update" data-neuro-install="1">'
                  '<p id="neuro-update-message"></p><progress id="neuro-update-progress" max="100" hidden></progress>'
                  '<div id="neuro-update-actions"></div></section><script>window.NEURO_INSTALL_CATALOG='
                  +json.dumps(catalog)+';</script><script>'+script+'</script></body></html>')
            document=Path(tmp)/'first-install.html';document.write_text(html,encoding='utf-8')
            env=dict(os.environ,NEURO_INSTALL_HTML=str(document),NEURO_PLAYWRIGHT_MODULE=PLAYWRIGHT,NEURO_BROWSER_EXECUTABLE=CHROME)
            result=subprocess.run([shutil.which('node'),str(ROOT/'tests/plugin_install_ui_browser.cjs')],env=env,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            print(result.stdout.strip())

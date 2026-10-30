"""Five test-phase tools reuse the host's interactive cards."""
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

from integration import radai_neuro_screen


ROOT = Path(__file__).resolve().parents[1]


def host_renderer():
    config_path = ROOT / 'neuro_rt.local.json'
    config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.is_file() else {}
    host = Path(os.environ.get('NEURO_HOST_ROOT', config.get('host_app', '')))
    source = host / 'app/radai_modules.py'
    if not source.is_file():
        source = host / 'radai_modules.py'
    if not source.is_file():
        raise unittest.SkipTest('Renderer do host indisponível.')
    spec = importlib.util.spec_from_file_location('neuro_availability_host_renderer', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ToolAvailabilityTests(unittest.TestCase):
    def test_all_tools_are_in_testing_and_returned_values_are_isolated(self):
        from neuro_rt.tool_availability import available_tools, require_tool, ToolUnavailable
        tools = available_tools()
        self.assertEqual(len(tools), 5)
        self.assertEqual([tool['id'] for tool in tools if tool['enabled']], ['nidus','glioma','metastasis','meningioma','anatomia'])
        for tool in tools:
            self.assertEqual(tool['label'], '[fase de testes]')
            self.assertEqual(tool['state'], 'testing')
            require_tool(tool['id'])
        tools[0]['enabled'] = False
        self.assertTrue(available_tools()[0]['enabled'])
        with self.assertRaises(ValueError):
            require_tool('unknown')

    def test_shared_host_cards_link_to_acknowledgement_without_mutating_host(self):
        renderer = host_renderer()
        before = repr(renderer.FERRAMENTAS)
        page = radai_neuro_screen._pagina_ferramentas(renderer)
        self.assertEqual(repr(renderer.FERRAMENTAS), before)
        for category in ('nidus', 'glioma', 'metastasis', 'meningioma', 'anatomia'):
            self.assertIn('href="/neuro/testing/' + category + '"', page)
        self.assertEqual(page.count('[fase de testes]'), 5)
        self.assertNotIn('class="md-fer obra" aria-disabled="true"', page)
        self.assertIn('.md-fer.obra{opacity:.62', page)

    def test_unrecognized_host_cards_fail_closed(self):
        renderer = host_renderer()
        renderer.FERRAMENTAS = dict(renderer.FERRAMENTAS)
        renderer.FERRAMENTAS['neuro'] = list(renderer.FERRAMENTAS['neuro']) + [
            ('unknown', 'contornos', 'Unknown', '/neuro/unknown', '', '')]
        with self.assertRaisesRegex(RuntimeError, 'ferramentas'):
            radai_neuro_screen._pagina_ferramentas(renderer)

    @unittest.skipUnless(shutil.which('node'), 'Node requerido para verificar navegador.')
    def test_active_cards_and_explicit_test_modal_in_real_browser(self):
        from integration.testing_access import page, policy
        tools = ('nidus','glioma','metastasis','meningioma','anatomia')
        base = ROOT/'runtime/test-tmp';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            fixture = Path(tmp)/'testing-fixture.json'
            fixture.write_text(json.dumps({'landing':radai_neuro_screen._pagina_ferramentas(host_renderer()),
                'pages':{t:page(t,False) for t in tools},'policies':{t:policy(t) for t in tools}}),encoding='utf-8')
            env=dict(os.environ,NEURO_TESTING_FIXTURE=str(fixture))
            run=subprocess.run([shutil.which('node'),str(ROOT/'tests/testing_access_ui_browser.cjs')],env=env,capture_output=True,timeout=90)
            self.assertEqual(run.returncode,0,run.stderr.decode(errors='replace')[-3000:])
            self.assertIn('PASS:',run.stdout.decode(errors='replace'))
            print(run.stdout.decode(errors='replace').strip())


if __name__ == '__main__':
    unittest.main()

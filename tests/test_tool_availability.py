"""Five resource-aware tools reuse the host's interactive cards."""
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
    def test_all_prepared_tools_are_ready_and_returned_values_are_isolated(self):
        from neuro_rt.tool_availability import available_tools, require_tool, ToolUnavailable
        tools = available_tools()
        self.assertEqual(len(tools), 5)
        self.assertEqual([tool['id'] for tool in tools if tool['enabled']], ['nidus','glioma','metastasis','meningioma','anatomia'])
        for tool in tools:
            self.assertEqual(tool['label'], '')
            self.assertEqual(tool['state'], 'ready')
            require_tool(tool['id'])
        tools[0]['enabled'] = False
        self.assertTrue(available_tools()[0]['enabled'])
        with self.assertRaises(ValueError):
            require_tool('unknown')

    def test_shared_host_cards_link_to_tools_without_mutating_host(self):
        renderer = host_renderer()
        before = repr(renderer.FERRAMENTAS)
        page = radai_neuro_screen._pagina_ferramentas(renderer)
        self.assertEqual(repr(renderer.FERRAMENTAS), before)
        for category in ('nidus', 'glioma', 'metastasis', 'meningioma', 'anatomia'):
            self.assertIn('href="/neuro/' + category + '"', page)
        self.assertNotIn('[fase de testes]', page)
        self.assertNotIn('class="md-fer obra" aria-disabled="true"', page)

    def test_unrecognized_host_cards_fail_closed(self):
        renderer = host_renderer()
        renderer.FERRAMENTAS = dict(renderer.FERRAMENTAS)
        renderer.FERRAMENTAS['neuro'] = list(renderer.FERRAMENTAS['neuro']) + [
            ('unknown', 'contornos', 'Unknown', '/neuro/unknown', '', '')]
        with self.assertRaisesRegex(RuntimeError, 'ferramentas'):
            radai_neuro_screen._pagina_ferramentas(renderer)

    def test_missing_models_keep_nidus_open_and_offer_weight_settings(self):
        from neuro_rt.tool_availability import available_tools
        page = radai_neuro_screen._pagina_ferramentas(host_renderer(), available_tools({'nidus'}))
        self.assertIn('href="/neuro/nidus"', page)
        self.assertEqual(page.count('href="/config#ps_neuro" data-neuro-models-missing'), 4)
        self.assertNotIn('href="/neuro/glioma"', page)
        self.assertIn('window.uiConfirmar', page)
        self.assertIn("location.assign('/config#ps_neuro')", page)

    def test_missing_models_popup_in_real_browser(self):
        from neuro_rt.tool_availability import available_tools
        playwright = os.environ.get('NEURO_PLAYWRIGHT_MODULE', '')
        if not shutil.which('node') or not Path(playwright).is_dir():
            self.skipTest('Chrome/Playwright indisponíveis.')
        with tempfile.TemporaryDirectory(prefix='neuro-missing-models-') as folder:
            fixture = Path(folder) / 'mini.html'
            fixture.write_text(radai_neuro_screen._pagina_ferramentas(
                host_renderer(), available_tools({'nidus'})), encoding='utf8')
            result = subprocess.run([shutil.which('node'), str(ROOT/'tests/missing_models_browser.cjs')],
                env=dict(os.environ, NEURO_MISSING_FIXTURE=str(fixture)),
                capture_output=True, text=True, encoding='utf8', errors='replace', timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS: Nidus open', result.stdout)

    def test_partial_anatomy_card_exposes_which_model_is_available(self):
        from neuro_rt.tool_availability import available_tools
        tools = available_tools({'nidus', 'anatomia'})
        anatomy = next(t for t in tools if t['id'] == 'anatomia')
        anatomy.update(state='partial', label='Buti')
        page = radai_neuro_screen._pagina_ferramentas(host_renderer(), tools)
        from html.parser import HTMLParser
        class Card(HTMLParser):
            def __init__(self):
                super().__init__()
                self.in_card = False
                self.text = []
            def handle_starttag(self, tag, attrs):
                if tag == 'a':
                    self.in_card = dict(attrs).get('href') == '/neuro/anatomia'
            def handle_endtag(self, tag):
                if tag == 'a':
                    self.in_card = False
            def handle_data(self, text):
                if self.in_card:
                    self.text.append(text)
        card = Card()
        card.feed(page)
        self.assertIn('Buti', card.text)


if __name__ == '__main__':
    unittest.main()

"""The staged delivery exposes Nidus while future tools remain inert."""
import importlib.util
import json
import os
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
    def test_only_nidus_is_available_and_returned_values_are_isolated(self):
        from neuro_rt.tool_availability import available_tools, require_tool, ToolUnavailable
        tools = available_tools()
        self.assertEqual(len(tools), 5)
        self.assertEqual([tool['id'] for tool in tools if tool['enabled']], ['nidus'])
        require_tool('nidus')
        for tool in tools:
            if tool['id'] != 'nidus':
                self.assertEqual(tool['label'], '[em construção]')
                with self.assertRaises(ToolUnavailable):
                    require_tool(tool['id'])
        tools[0]['enabled'] = False
        self.assertTrue(available_tools()[0]['enabled'])
        with self.assertRaises(ValueError):
            require_tool('unknown')

    def test_shared_host_cards_are_inert_without_mutating_host(self):
        renderer = host_renderer()
        before = repr(renderer.FERRAMENTAS)
        page = radai_neuro_screen._pagina_ferramentas(renderer)
        self.assertEqual(repr(renderer.FERRAMENTAS), before)
        self.assertIn('href="/neuro/nidus"', page)
        for category in ('glioma', 'metastasis', 'meningioma', 'anatomia'):
            self.assertNotIn('href="/neuro/' + category + '"', page)
        self.assertEqual(page.count('[em construção]'), 4)
        self.assertEqual(page.count('class="md-fer obra" aria-disabled="true"'), 4)
        self.assertNotIn('tabindex=', page)
        self.assertIn('.md-fer.obra{opacity:.62', page)

    def test_unrecognized_host_cards_fail_closed(self):
        renderer = host_renderer()
        renderer.FERRAMENTAS = dict(renderer.FERRAMENTAS)
        renderer.FERRAMENTAS['neuro'] = list(renderer.FERRAMENTAS['neuro']) + [
            ('unknown', 'contornos', 'Unknown', '/neuro/unknown', '', '')]
        with self.assertRaisesRegex(RuntimeError, 'ferramentas'):
            radai_neuro_screen._pagina_ferramentas(renderer)


if __name__ == '__main__':
    unittest.main()

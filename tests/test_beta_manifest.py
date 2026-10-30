import json
import tempfile
import unittest
from pathlib import Path
from neuro_rt.plugin_manifest import read_manifest, check_host_compatibility

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ['nidus', 'glioma', 'metastasis', 'meningioma', 'anatomia']

class BetaManifestTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'module.json'
        self.value = json.loads((ROOT / 'module.json').read_text(encoding='utf-8'))
        self.value.update(version='1.1.0',host_min_version='8.12',enabled_tools=TOOLS,
                          resource_recipe='catalog/resource_recipe.json')
    def read(self, **changes):
        self.path.write_text(json.dumps(dict(self.value, **changes)), encoding='utf-8')
        return read_manifest(self.path)
    def test_five_tools_share_host_with_a_code_only_resource_recipe(self):
        manifest = self.read()
        self.assertEqual(manifest.enabled_tools, tuple(TOOLS))
        self.assertEqual(manifest.resource_recipe, 'catalog/resource_recipe.json')
        self.assertFalse(check_host_compatibility(manifest, {'contract':manifest.host_contract,'version':'8.11'}).compatible)
        self.assertTrue(check_host_compatibility(manifest, {'contract':manifest.host_contract,'version':'8.12'}).compatible)
    def test_incomplete_tools_old_host_or_private_payload_never_form_beta_profile(self):
        for changes in ({'enabled_tools':['nidus','glioma']}, {'enabled_tools':TOOLS+['unknown']},
                        {'host_min_version':'8.11'}, {'version':'1.0.2'},
                        {'resource_recipe':'../outside.json'}, {'resource_recipe':None},
                        {'artifacts':[{'path':'weights.bin'}]},
                        {'runtimes':{'other':{'python':'python.exe'}}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.read(**changes)

if __name__ == '__main__': unittest.main()

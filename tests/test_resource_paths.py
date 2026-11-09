"""Host resource descriptor validation, without importing scientific modules."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from neuro_rt.plugin_paths import resolve_plugin_paths

def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)+'\n').encode()

class ResourcePathsTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.host = Path(self.tmp.name)
        self.plugin = self.host / 'Plugins/NEURO RT'
        self.code = self.plugin / 'versions/1.1.0'
        (self.code/'catalog').mkdir(parents=True)
        recipe = {'schema':'neuro-rt/resource-recipe/1','models':[]}
        (self.code/'catalog/resource_recipe.json').write_bytes(canonical(recipe))
        (self.code/'catalog/models.json').write_text(json.dumps({'models':[
            {'id':'phantom','revision':'1.0','catalog_state':'distributed'}]}))
        digest = hashlib.sha256(canonical(recipe)).hexdigest()
        receipt = {'schema':'neuro-rt/resolved-resources/1','recipe_digest':digest,
            'extras_digest':'e'*64,'extras_relative_path':'extras/'+ 'e'*64+'/site-packages',
            'model_relative_paths':{'phantom':'models/phantom/1.0'},
            'capabilities':{'phantom':{'available':True,'reason':''}}}
        self.receipt = self.plugin / ('resources/'+digest+'.json')
        self.receipt.parent.mkdir(parents=True)
        self.receipt.write_bytes(canonical(receipt))
        (self.plugin/receipt['extras_relative_path']).mkdir(parents=True)
        (self.plugin/'models/phantom/1.0').mkdir(parents=True)
        self.descriptor = dict(receipt, receipt_relative_path='resources/'+digest+'.json',
            receipt_sha256=hashlib.sha256(self.receipt.read_bytes()).hexdigest())
        self.state = {'state':'ready','execution_mode':'host','active_version':'1.1.0',
                      'runtime':None,'resources':self.descriptor}
        self.binding = patch('importlib.metadata.version', return_value='1.0')
        self.binding.start(); self.addCleanup(self.binding.stop)

    def paths(self, **changes):
        return resolve_plugin_paths(self.host, dict(self.state, **changes), host_python=sys.executable)

    def test_binds_only_verified_resource_paths_without_selecting_an_interpreter(self):
        paths = self.paths()
        self.assertEqual(paths.worker_python, Path(sys.executable).resolve())
        self.assertEqual(paths.extras_dir, self.plugin/self.descriptor['extras_relative_path'])
        self.assertEqual(paths.resources_file, self.receipt)
        self.assertEqual(paths.resources['recipe_digest'], self.descriptor['recipe_digest'])

    def test_adulterated_receipt_recipe_or_catalog_path_never_mounts(self):
        for changes in ({'extras_relative_path':'../outside'}, {'receipt_relative_path':'../other'},
                        {'recipe_digest':'a'*64}, {'receipt_sha256':'0'*64},
                        {'model_relative_paths':{'phantom':'models/phantom/other'}},
                        {'host_python':sys.executable}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.paths(resources=dict(self.descriptor, **changes))
        self.receipt.write_bytes(self.receipt.read_bytes()+b' ')
        with self.assertRaises(ValueError): self.paths()

    def test_missing_resources_keeps_legacy_nidus_profile_but_extras_absent(self):
        paths = self.paths(resources=None, active_version='1.0.2')
        self.assertIsNone(paths.extras_dir)
        self.assertIsNone(paths.resources_file)
        self.assertIsNone(paths.resources)
        with self.assertRaises(ValueError): self.paths(resources=None)

    def test_existing_host_model_never_requires_a_second_copy(self):
        catalog_file = self.code / 'catalog/models.json'
        catalog = json.loads(catalog_file.read_text())
        catalog['models'].append({'id':'cranio_buti','revision':'host',
                                  'catalog_state':'distributed','host_managed':True})
        catalog_file.write_text(json.dumps(catalog))
        self.assertEqual(self.paths().resources['model_relative_paths'], {'phantom':'models/phantom/1.0'})

    def test_verified_additions_use_the_same_confined_model_contract(self):
        catalog_file = self.code / 'catalog/models.json'
        catalog = json.loads(catalog_file.read_text())
        catalog['models'][0]['catalog_state'] = 'verified'
        catalog_file.write_text(json.dumps(catalog))
        self.assertEqual(self.paths().resources['model_relative_paths'], {'phantom':'models/phantom/1.0'})

if __name__ == '__main__': unittest.main()

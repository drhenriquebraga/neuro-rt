"""The host pin is injected outside CODE and never inferred from local hashes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from host_setup_fixtures import host_setup
from scripts.build_host_bootstrap import generate


class ExternalBootstrapTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        base = root / 'runtime/test-tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        package = host_setup(self.root)
        self.source = self.root / 'offline'
        with zipfile.ZipFile(package['path']) as archive:
            archive.extractall(self.source)
        manifest = json.loads((self.source / 'release-manifest.json').read_text())
        records = sorted(manifest['files'], key=lambda record: record['path'])
        self.pin = hashlib.sha256((json.dumps(records, sort_keys=True, separators=(',', ':')) + '\n').encode()).hexdigest()

    def load(self, path):
        spec = importlib.util.spec_from_file_location('external_bootstrap_fixture', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_generated_host_exposes_three_sdk_functions_and_pins_code(self):
        path = generate(self.root / 'bootstrap.py', trusted_code_inventory_sha=self.pin)
        with patch.dict(sys.modules):
            for name in list(sys.modules):
                if name.startswith('_radai_neuro_bootstrap'):
                    sys.modules.pop(name)
            before = set(sys.modules)
            module = self.load(path)
            self.assertEqual(module.inspect_local_source(self.source)['code_inventory_sha256'], self.pin)
            plan = module.prepare_external_plan(module.inspect_local_source(self.source), source_folder=self.source)
            self.assertEqual(plan['schema'], 'neuro-rt/external-plan/1')
            self.assertTrue(callable(module.run_external))
            heavy = {'numpy', 'scipy', 'SimpleITK', 'torch', 'onnxruntime', 'PIL', 'ants', 'dipy'}
            self.assertFalse({name.split('.')[0] for name in set(sys.modules) - before} & heavy)
        self.assertIn(self.pin, path.read_text(encoding='utf-8'))
        sdk = Path(__file__).resolve().parents[1] / 'neuro_rt/external_install.py'
        self.assertNotIn(self.pin, sdk.read_text(encoding='utf-8'))

    def test_invalid_pin_is_rejected_before_writing_host_bootstrap(self):
        target = self.root / 'invalid.py'
        with self.assertRaises(ValueError):
            generate(target, trusted_code_inventory_sha='adjacent checksum is not authority')
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()

"""Workers reuse one interpreter and append only authenticated missing extras."""
import json
import os
import importlib.util
import importlib._bootstrap_external
from pathlib import Path
import sys
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from neuro_rt.service import Settings
from neuro_rt.process_tree import ManagedProcess
from neuro_rt import resource_preparation
try:
    from neuro_rt import worker_bootstrap
except ImportError:
    worker_bootstrap = None


class HostWorkerResourcesTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='worker resources ', dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.code = self.root / 'code'
        (self.code / 'catalog').mkdir(parents=True)
        self.plugin = self.root / 'plugin'
        self.recipe = {'schema': 'neuro-rt/resource-recipe/1', 'version': 'test',
                       'protected_base': {}, 'wheels': [], 'downloads': {}, 'models': [], 'adapters': {}}
        (self.code / 'catalog/resource_recipe.json').write_bytes(resource_preparation.canonical_bytes(self.recipe))
        (self.code / 'catalog/models.json').write_text('{"schema":"neuro-rt/catalog/1","models":[]}')
        with patch.object(resource_preparation, 'validate_host_runtime', return_value=Path(sys.executable)):
            self.resources = resource_preparation.prepare_resources(self.recipe, plugin_root=self.plugin,
                host_python=sys.executable, source_folder=self.root)

    def settings(self, resources=None):
        values = self.resources if resources is None else resources
        paths = SimpleNamespace(code_dir=self.code, worker_python=Path(sys.executable),
            models_dir=self.plugin / 'models', data_dir=self.plugin / 'data', host_root=self.root,
            plugin_root=self.plugin, execution_mode='host', resources=values,
            extras_dir=self.plugin / self.resources['extras_relative_path'],
            resources_file=self.plugin / self.resources['receipt_relative_path'],
            state=SimpleNamespace(value='ready'))
        return Settings(self.code, plugin_paths=paths)

    def test_ready_scientific_runtime_uses_exactly_the_host_executable(self):
        descriptor = dict(self.resources, capabilities={'raidionics': {'available': True, 'reason': ''},
                                                       'attention_unet': {'available': True, 'reason': ''},
                                                       'buti_host': {'available': True, 'reason': ''}})
        settings = self.settings(descriptor)
        for runtime in ('raidionics-onnx', 'neuro-scientific-cpu', 'host-nnunet'):
            self.assertEqual(settings.runtime_python(runtime), str(Path(sys.executable)))
        self.assertIsNone(settings.runtime_python('unknown'))

    def test_no_resources_or_missing_capability_never_claims_model_ready(self):
        settings = self.settings({})
        self.assertTrue(hasattr(settings, 'model_runtime_status'))
        status = settings.model_runtime_status({'adapter_id': 'raidionics', 'runtime_id': 'raidionics-onnx'})
        self.assertFalse(status['available'])
        self.assertTrue(status['reason'])

    def test_worker_command_explicitly_loads_code_with_host_interpreter(self):
        settings = self.settings()
        self.assertTrue(hasattr(settings, 'worker_command'))
        command = settings.worker_command('study', ['--task', 'prepare', '--job-dir', str(self.root / 'job')],
                                          preparation=True)
        self.assertEqual(command[0], str(Path(sys.executable)))
        self.assertIn('-I', command)
        self.assertIn('-B', command)
        self.assertIn(str(self.code), command)
        self.assertIn('neuro_rt.worker_bootstrap', command[command.index('-c') + 1])

    def test_authenticated_overlay_is_appended_after_existing_base_paths(self):
        self.assertIsNotNone(worker_bootstrap, 'The explicit worker bootstrap is missing.')
        before = list(sys.path)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), before))
        target = worker_bootstrap.activate_resources(self.code, self.plugin, self.resources)
        self.assertEqual(sys.path[:len(before)], before)
        self.assertEqual(sys.path[-1], str(target))

    def test_uninventoried_extra_source_is_rejected_before_import_path_changes(self):
        self.assertIsNotNone(worker_bootstrap, 'The explicit worker bootstrap is missing.')
        extra = self.plugin / self.resources['extras_relative_path']
        (extra / 'untrusted.py').write_text('raise RuntimeError("untrusted")')
        before = list(sys.path)
        with self.assertRaises(ValueError):
            worker_bootstrap.activate_resources(self.code, self.plugin, self.resources)
        self.assertEqual(sys.path, before)

    def test_export_and_views_resolve_in_embedded_python_outside_code_directory(self):
        settings = self.settings()
        settings.root = Path(__file__).resolve().parents[1]
        for module in ('export', 'views', 'legacy-export', 'legacy-views'):
            with self.subTest(module=module):
                command = settings.worker_command(module, ['--help'], preparation=True)
                self.assertEqual(command[0], str(Path(sys.executable)))
                self.assertNotIn('--resources', command)
                result = subprocess.run(command, cwd=self.root, capture_output=True, text=True,
                                        encoding='utf-8', errors='replace', timeout=45)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('--job-dir', result.stdout)

    def test_managed_export_preserves_isolation_and_runs_the_explicit_code_bootstrap(self):
        settings = self.settings()
        settings.root = Path(__file__).resolve().parents[1]
        command = settings.worker_command('export', ['--help'], preparation=True)
        target = self.root / 'managed export.log'
        with target.open('wb') as log:
            managed = ManagedProcess(command, cwd=self.root, env=dict(os.environ), stdout=log)
            try:
                result = managed.wait(timeout=45)
            finally:
                managed.close()
        output = target.read_text(encoding='utf-8', errors='replace')
        self.assertEqual(result, 0, output)
        self.assertIn('--job-dir', output)

    def test_managed_interpreter_flags_are_applied_before_the_ownership_entrypoint(self):
        marker = self.root / 'isolated flags.json'
        command = [sys.executable, '-I', '-B', '-u', '-c',
                   'import sys,json;from pathlib import Path;'
                   'Path(sys.argv[1]).write_text(json.dumps({"isolated":sys.flags.isolated,'
                   '"dont_write_bytecode":sys.dont_write_bytecode}),encoding="utf-8")', str(marker)]
        with (self.root / 'managed flags.log').open('wb') as log:
            managed = ManagedProcess(command, cwd=self.root, env=dict(os.environ), stdout=log)
            try:
                result = managed.wait(timeout=20)
            finally:
                managed.close()
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(marker.read_text()), {'isolated': 1, 'dont_write_bytecode': True})

    def test_unverified_timestamp_pyc_cannot_execute_in_real_embedded_worker(self):
        from test_resource_preparation import ResourcePreparationTests
        (self.root / 'downloads').mkdir()
        helper = SimpleNamespace(source=self.root, recipe=self.recipe)
        ResourcePreparationTests.wheel(helper)
        (self.code / 'catalog/resource_recipe.json').write_bytes(resource_preparation.canonical_bytes(self.recipe))
        with patch.object(resource_preparation, 'validate_host_runtime', return_value=Path(sys.executable)):
            descriptor = resource_preparation.prepare_resources(self.recipe, plugin_root=self.plugin,
                host_python=sys.executable, source_folder=self.root)
        source = self.plugin / descriptor['extras_relative_path'] / 'neuro_extra_fixture/__init__.py'
        marker = self.root / 'UNVERIFIED_PYC_EXECUTED'
        malicious = compile('from pathlib import Path\nPath(' + repr(str(marker)) +
                            ').write_text("UNVERIFIED_PYC")\nVALUE="UNVERIFIED_PYC"\n', str(source), 'exec')
        bytecode = importlib._bootstrap_external._code_to_timestamp_pyc(
            malicious, int(source.stat().st_mtime), source.stat().st_size)
        target = Path(importlib.util.cache_from_source(str(source)))
        target.parent.mkdir()
        target.write_bytes(bytecode)
        entry = ('import sys,json;sys.path.insert(0,sys.argv[1]);'
                 'from neuro_rt.worker_bootstrap import activate_resources;'
                 'activate_resources(sys.argv[2],sys.argv[3],json.loads(sys.argv[4]));'
                 'import neuro_extra_fixture;print(neuro_extra_fixture.VALUE)')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', entry,
            str(Path(__file__).resolve().parents[1]), str(self.code), str(self.plugin), json.dumps(descriptor)],
            cwd=self.root, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=45)
        self.assertFalse(marker.exists(), result.stdout + result.stderr)
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()

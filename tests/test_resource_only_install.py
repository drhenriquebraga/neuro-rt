"""Resource-only maintenance keeps authenticated active CODE and user data."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import test_code_only_install as code_fixture
import test_external_install as external_fixture
from neuro_rt import external_install as external, install_state


class ResourceOnlyTests(unittest.TestCase):
    plan = code_fixture.CodeOnlyTests.plan
    run_plan = code_fixture.CodeOnlyTests.run_plan

    def setUp(self):
        code_fixture.CodeOnlyTests.setUp(self)
        self.run_plan(self.plan())
        self.plugin = self.host / 'Plugins/NEURO RT'
        self.pointer = self.plugin / 'installation.json'
        self.bundle = self.root / 'older-offline-bundle'
        shutil.copytree(self.source, self.bundle)
        manifest_path = self.bundle / 'release-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        module_path = self.bundle / 'code/module.json'
        module = json.loads(module_path.read_text())
        module['version'] = '1.3.0'
        module.pop('base_tools', None)
        module_path.write_text(json.dumps(module), encoding='utf8')
        manifest['version'] = '1.3.0'
        for record in manifest['files']:
            data = (self.bundle / record['path']).read_bytes()
            record.update(size=len(data), sha256=hashlib.sha256(data).hexdigest())
        manifest_path.write_text(json.dumps(manifest), encoding='utf8')
        (self.bundle / 'offline-bundle.json').write_text(json.dumps({
            'schema': 'neuro-rt/local-bundle/1', 'version': '1.3.0'}), encoding='utf8')
        pin = external.code_inventory_sha256(manifest)
        patcher = patch.object(external, 'TRUSTED_CODE_INVENTORIES',
                               set(external.TRUSTED_CODE_INVENTORIES) | {pin})
        patcher.start()
        self.addCleanup(patcher.stop)

    def resource_plan(self, **changes):
        return external.prepare_external_plan(dict(mode='local', local_source_accepted=True,
            resources_only=True, **changes), source_folder=self.bundle)

    def prepare_resources(self, *args, **kwargs):
        return external_fixture.ExternalInstallTests.prepared_resources(self, *args, **kwargs)

    def test_older_bundle_installs_resources_without_downgrading_or_replacing_code(self):
        before = json.loads(self.pointer.read_text())
        inventory = self.plugin / 'versions/1.3.2/release-manifest.json'
        code_before = inventory.read_bytes()
        (self.plugin / 'data/keep.txt').write_text('synthetic preserved')
        events = []
        with patch.object(external, '_prepare_resources', side_effect=self.prepare_resources) as prepare, \
                patch.object(install_state, 'begin_install', side_effect=AssertionError('CODE install forbidden')), \
                patch.object(install_state, 'activate_release', side_effect=AssertionError('CODE activation forbidden')), \
                patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')), \
                patch('importlib.metadata.version', return_value='1.0'):
            result = external.run_external(self.resource_plan(), events.append,
                suite_root=self.host, host_python=sys.executable)
        after = json.loads(self.pointer.read_text())
        self.assertEqual(result['active_version'], before['active_version'])
        self.assertEqual(after['active_version'], '1.3.2')
        self.assertEqual(after['resource_bundle_version'], '1.3.0')
        self.assertEqual(prepare.call_args.kwargs['source_folder'], self.bundle)
        self.assertEqual(inventory.read_bytes(), code_before)
        self.assertEqual((self.plugin / 'data/keep.txt').read_text(), 'synthetic preserved')
        self.assertFalse((self.plugin / 'versions/1.3.0').exists())
        self.assertEqual(events[-1]['version'], '1.3.2')
        self.assertEqual(events[-1]['resource_bundle_version'], '1.3.0')

    def test_failed_resource_only_install_keeps_active_pointer_identical(self):
        before = self.pointer.read_bytes()
        with patch.object(external, '_prepare_resources', side_effect=OSError('synthetic failure')), \
                patch('importlib.metadata.version', return_value='1.0'):
            with self.assertRaises(OSError):
                external.run_external(self.resource_plan(), None,
                    suite_root=self.host, host_python=sys.executable)
        self.assertEqual(self.pointer.read_bytes(), before)

    def test_code_only_update_preserves_resource_bundle_identity(self):
        with patch.object(external, '_prepare_resources', side_effect=self.prepare_resources):
            self.run_plan(self.resource_plan())
        before = json.loads(self.pointer.read_text())
        self.run_plan(self.plan())
        after = json.loads(self.pointer.read_text())
        self.assertEqual(after['resource_bundle_version'], '1.3.0')
        self.assertEqual(after['resources'], before['resources'])

    def test_resource_only_is_boolean_and_separate_from_code_only(self):
        for value in (None, 0, 'true', []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                external.prepare_external_plan({'mode': 'local', 'local_source_accepted': True,
                    'resources_only': value}, source_folder=self.bundle)
        with self.assertRaises(ValueError):
            self.resource_plan(code_only=True)


if __name__ == '__main__':
    unittest.main()

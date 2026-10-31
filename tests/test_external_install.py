"""External maintenance uses trusted arguments and small synthetic CODE only."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from host_setup_fixtures import host_setup
from neuro_rt import external_install as external
from neuro_rt import install_state


class ExternalInstallTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / 'runtime/test-tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

        def recipe(manifest, files):
            module = json.loads(files['code/module.json'])
            module['host_min_version'] = '8.12'
            module['enabled_tools'] = ['nidus', 'glioma', 'metastasis', 'meningioma', 'anatomia']
            module['resource_recipe'] = 'catalog/resource_recipe.json'
            files['code/module.json'] = json.dumps(module).encode()
            files['code/catalog/resource_recipe.json'] = json.dumps({
                'schema': 'neuro-rt/resource-recipe/1', 'wheels': [], 'models': []}).encode()

        self.package = host_setup(self.root, '1.1.0', mutate=recipe)
        self.source = self.root / 'transport'
        with zipfile.ZipFile(self.package['path']) as archive:
            archive.extractall(self.source)  # Invented fixture, never user input.
        self.manifest = json.loads((self.source / 'release-manifest.json').read_text())
        records = sorted(self.manifest['files'], key=lambda record: record['path'])
        canonical = (json.dumps(records, sort_keys=True, ensure_ascii=True,
                                separators=(',', ':')) + '\n').encode()
        self.inventory_sha = hashlib.sha256(canonical).hexdigest()
        self.pin = patch.object(external, 'TRUSTED_CODE_INVENTORIES', {self.inventory_sha})
        self.pin.start()
        self.addCleanup(self.pin.stop)
        self.host = self.root / 'Suite sintética á'
        self.host.mkdir()
        for name, text in (('radai_panel.py', '# fixture'), ('radai_ui.py', '# fixture'),
                           ('entrega.txt', 'VERSAO=8.12\n')):
            (self.host / name).write_text(text)

    def plan(self):
        return external.prepare_external_plan({'mode': 'local', 'local_source_accepted': True},
                                              source_folder=self.source)

    def prepared_resources(self, recipe, *, plugin_root, **kwargs):
        recipe_sha = hashlib.sha256(external._json(recipe)).hexdigest()
        extras_sha = 'a' * 64
        values = {'schema': 'neuro-rt/resolved-resources/1', 'recipe_digest': recipe_sha,
                  'extras_digest': extras_sha, 'extras_relative_path': 'extras/' + extras_sha + '/site-packages',
                  'model_relative_paths': {}, 'capabilities': {'nidus': {'available': True, 'reason': ''}}}
        (plugin_root / values['extras_relative_path']).mkdir(parents=True, exist_ok=True)
        receipt = plugin_root / ('resources/' + recipe_sha + '.json')
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_bytes(external._json(values))
        return dict(values, receipt_relative_path=receipt.relative_to(plugin_root).as_posix(),
                    receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest())

    def test_local_inspection_requires_pinned_inventory_and_all_file_hashes(self):
        description = external.inspect_local_source(self.source)
        self.assertEqual(description['version'], '1.1.0')
        self.assertEqual(description['code_inventory_sha256'], self.inventory_sha)
        self.assertEqual(description['trust'], 'host-pinned-code')
        self.assertEqual(description['kind'], 'setup')
        self.assertFalse(description['resources_verified'])
        with patch.object(external, 'TRUSTED_CODE_INVENTORIES', set()):
            with self.assertRaises(ValueError): external.inspect_local_source(self.source)
        (self.source / 'code/integration/radai_neuro.py').write_text('tampered')
        with self.assertRaises(ValueError): external.inspect_local_source(self.source)

    def test_adjacent_manifest_rehash_does_not_authorize_altered_code(self):
        target = self.source / 'code/integration/radai_neuro.py'
        target.write_bytes(b'synthetic changed code')
        for record in self.manifest['files']:
            if record['path'] == 'code/integration/radai_neuro.py':
                record.update(size=target.stat().st_size, sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        (self.source / 'release-manifest.json').write_text(json.dumps(self.manifest))
        with self.assertRaises(ValueError): external.inspect_local_source(self.source)

    def test_plan_is_strict_serializable_and_does_not_accept_host_or_executable(self):
        plan = self.plan()
        self.assertEqual(json.loads(json.dumps(plan)), plan)
        self.assertEqual(plan['schema'], 'neuro-rt/external-plan/1')
        self.assertEqual(plan['mode'], 'local')
        self.assertEqual(plan['version'], '1.1.0')
        self.assertEqual(len(plan['transaction_id']), 32)
        for key in ('suite_root', 'host_python', 'script', 'command'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                external.prepare_external_plan({'mode': 'local', 'local_source_accepted': True,
                                                key: 'untrusted'}, source_folder=self.source)
        with self.assertRaises(ValueError):
            external.prepare_external_plan({'mode': 'local'}, source_folder=self.source)

    def test_tampered_plan_and_changed_source_are_rejected_before_install(self):
        plan = self.plan()
        with patch.object(install_state, 'begin_install', side_effect=AssertionError('Must not install')):
            bad = copy.deepcopy(plan)
            bad['host_python'] = 'remote/python.exe'
            with self.assertRaises(ValueError):
                external.run_external(bad, None, suite_root=self.host, host_python=sys.executable)
            (self.source / 'code/integration/radai_neuro.py').write_text('changed after inspection')
            with self.assertRaises(ValueError):
                external.run_external(plan, None, suite_root=self.host, host_python=sys.executable)

    def test_real_code_prepare_resources_and_activation_do_not_require_restart(self):
        events = []
        with patch('importlib.metadata.version', return_value='1.0'), \
                patch.object(external, '_prepare_resources', side_effect=self.prepared_resources) as resources:
            result = external.run_external(self.plan(), events.append,
                                           suite_root=self.host, host_python=sys.executable)
        self.assertEqual(result['state'], 'ready')
        self.assertEqual(result['active_version'], '1.1.0')
        state = json.loads((self.host / 'Plugins/NEURO RT/installation.json').read_text())
        self.assertEqual(state['active_version'], '1.1.0')
        self.assertEqual(state['resources']['schema'], 'neuro-rt/resolved-resources/1')
        self.assertIsNone(state['pending_resources'])
        self.assertEqual(resources.call_args.kwargs['source_folder'], self.source.resolve())
        self.assertIn('activating', [event['state'] for event in events])
        self.assertEqual(events[-1]['state'], 'ready')
        self.assertFalse((self.host / 'python').exists())

    def test_resource_failure_preserves_previous_active_version_and_user_data(self):
        old = host_setup(self.root, '1.0.2')
        with patch('importlib.metadata.version', return_value='1.0'):
            install_state.begin_install(self.host, old, 'previous', host_python=sys.executable)
            install_state.activate_release(self.host / 'Plugins/NEURO RT', '1.0.2', host_python=sys.executable)
        keep = self.host / 'Plugins/NEURO RT/data/keep.txt'
        keep.write_text('synthetic preserved')
        with patch('importlib.metadata.version', return_value='1.0'), \
                patch.object(external, '_prepare_resources', side_effect=OSError('synthetic interrupted download')):
            with self.assertRaises(OSError):
                external.run_external(self.plan(), None, suite_root=self.host, host_python=sys.executable)
        state = json.loads((self.host / 'Plugins/NEURO RT/installation.json').read_text())
        self.assertEqual(state['active_version'], '1.0.2')
        self.assertEqual(keep.read_text(), 'synthetic preserved')

    def test_online_plan_selects_owned_setup_identity_without_downloading(self):
        release = {'state': 'available', 'release_id': 23, 'asset_id': 7,
            'name': 'NEURO_RT_SETUP_v1.1.0.zip', 'version': '1.1.0', 'size': 1000,
            'url': 'https://api.github.com/repos/drhenriquebraga/neuro-rt/releases/assets/7',
            'sha256': 'a'*64, 'package_kind': 'setup'}
        plan = external.prepare_external_plan({'mode': 'online', 'release': release})
        self.assertEqual(plan['mode'], 'online')
        self.assertEqual(plan['source']['sha256'], 'a'*64)
        bad = dict(release, name='NEURO_RT_OFFLINE_v1.1.0.zip')
        with self.assertRaises(ValueError):
            external.prepare_external_plan({'mode': 'online', 'release': bad})

    def test_pinned_description_action_and_cancellation_are_explicit(self):
        description = external.inspect_local_source(self.source)
        plan = external.prepare_external_plan(dict(description, action='update'), source_folder=self.source)
        self.assertEqual(plan['action'], 'update')
        with patch('importlib.metadata.version', return_value='1.0'), \
                patch.object(install_state, 'begin_install', side_effect=AssertionError('Cancelled before prepare')):
            with self.assertRaises(install_state.InstallFailure) as stopped:
                external.run_external(plan, lambda _: False, suite_root=self.host, host_python=sys.executable)
        self.assertEqual(stopped.exception.error_code, 'CANCELLED')
        bad = dict(plan, action='execute_script')
        with self.assertRaises(ValueError):
            external.run_external(bad, None, suite_root=self.host, host_python=sys.executable)

    def test_all_five_tools_require_the_pinned_resource_recipe_in_inventory(self):
        def beta(manifest, files):
            module = json.loads(files['code/module.json'])
            module.update(host_min_version='8.12',
                          enabled_tools=['nidus', 'glioma', 'metastasis', 'meningioma', 'anatomia'],
                          resource_recipe='catalog/resource_recipe.json')
            files['code/module.json'] = json.dumps(module).encode()
            files['code/catalog/resource_recipe.json'] = json.dumps({
                'schema': 'neuro-rt/resource-recipe/1', 'wheels': [], 'models': []}).encode()
        package = host_setup(self.root, '1.1.0', mutate=beta)
        with patch('importlib.metadata.version', return_value='1.0'):
            receipt = install_state.begin_install(self.host, package, 'beta', host_python=sys.executable)
        self.assertEqual(receipt.version, '1.1.0')

    def test_final_status_or_callback_failure_cannot_invalidate_committed_activation(self):
        atomic = install_state._atomic_json
        def deny_final(path, value):
            if Path(path).name == 'external-status.json' and value.get('state') == 'ready':
                raise PermissionError('synthetic final progress denied')
            return atomic(path, value)
        def broken_final(event):
            if event['state'] == 'ready':
                raise RuntimeError('synthetic final consumer failure')
        with patch('importlib.metadata.version', return_value='1.0'), \
                patch.object(external, '_prepare_resources', side_effect=self.prepared_resources), \
                patch.object(install_state, '_atomic_json', side_effect=deny_final):
            result = external.run_external(self.plan(), broken_final,
                                           suite_root=self.host, host_python=sys.executable)
        self.assertEqual(result, {'state': 'ready', 'active_version': '1.1.0'})
        state = json.loads((self.host / 'Plugins/NEURO RT/installation.json').read_text())
        self.assertEqual(state['active_version'], '1.1.0')

    def test_unextracted_or_parent_folder_has_a_controlled_extraction_hint(self):
        with self.assertRaises(ValueError) as failure:
            external.inspect_local_source(self.root)
        self.assertEqual(failure.exception.source_hint, 'extract_setup')
        self.assertIn('release-manifest.json', str(failure.exception))
        self.assertIn('START_HERE.cmd', str(failure.exception))

    def test_local_materialization_is_byte_stable_for_retry_of_the_same_plan(self):
        plan = self.plan()
        first, second = self.root / 'first.zip', self.root / 'second.zip'
        with patch('zipfile.time.localtime', return_value=(2020, 1, 1, 0, 0, 0, 2, 1, 0)):
            one = external._local_package(plan, first)
        with patch('zipfile.time.localtime', return_value=(2025, 1, 1, 0, 0, 0, 2, 1, 0)):
            two = external._local_package(plan, second)
        self.assertEqual(one['sha256'], two['sha256'])
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_lower_level_beta_activation_requires_its_pending_resource_receipt(self):
        with patch('importlib.metadata.version', return_value='1.0'):
            install_state.begin_install(self.host, self.package, 'beta-no-resources', host_python=sys.executable)
            with self.assertRaises(ValueError):
                install_state.activate_release(self.host / 'Plugins/NEURO RT', '1.1.0', host_python=sys.executable)
        state = json.loads((self.host / 'Plugins/NEURO RT/installation.json').read_text())
        self.assertIsNone(state['active_version'])

    def test_new_pending_version_clears_stale_resources_and_legacy_activation_drops_them(self):
        old = host_setup(self.root, '1.0.2')
        plugin = self.host / 'Plugins/NEURO RT'
        with patch('importlib.metadata.version', return_value='1.0'):
            install_state.begin_install(self.host, old, 'legacy', host_python=sys.executable)
            path = plugin / 'installation.json'
            state = json.loads(path.read_text())
            state.update(resources={'stale': True}, pending_resources={'stale': True})
            path.write_text(json.dumps(state))
            install_state.begin_install(self.host, self.package, 'beta', host_python=sys.executable)
            self.assertIsNone(json.loads(path.read_text())['pending_resources'])
            install_state.activate_release(plugin, '1.0.2', host_python=sys.executable)
        self.assertIsNone(json.loads(path.read_text())['resources'])
        self.assertIsNone(json.loads(path.read_text())['pending_resources'])

    def test_legacy_cli_refuses_beta_code_only_preparation_before_install(self):
        import contextlib
        import io
        from neuro_rt import plugin_update
        output = io.StringIO()
        with patch('neuro_rt.plugin_consent.accepted', return_value=True), \
                patch.object(install_state, 'begin_install', side_effect=AssertionError('Beta needs external resources/lifecycle')), \
                contextlib.redirect_stdout(output):
            result = plugin_update.main(['--suite-root', str(self.host), '--host-version', '8.12',
                '--package-path', self.package['path'], '--package-sha256', self.package['sha256']])
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(output.getvalue())['error_code'], 'EXTERNAL_MAINTENANCE_REQUIRED')

    def test_resource_progress_preserves_safe_stages_components_and_counters_in_both_modes(self):
        import io
        from neuro_rt import plugin_update, resource_preparation
        weight, license_text = b'invented pinned resource', b'MIT fixture license'
        wheel = json.loads((Path(__file__).resolve().parents[1] / 'catalog/resource_recipe.json').read_text())['wheels'][0]
        def spec(filename, raw):
            return {'filename': filename, 'url': 'https://example.invalid/' + filename,
                    'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        downloads = {'weight': spec('weights.bin', weight), 'license': spec('license.txt', license_text)}
        recipe = {'schema': 'neuro-rt/resource-recipe/1', 'protected_base': {}, 'wheels': [wheel],
            'downloads': downloads, 'adapters': {}, 'models': [{'id': 'fixture-model', 'revision': '1',
                'files': {'weights.bin': dict(download='weight', size=len(weight), sha256=downloads['weight']['sha256']),
                          'LICENSE.txt': dict(download='license', size=len(license_text), sha256=downloads['license']['sha256'])},
                'license_paths': ['LICENSE.txt'], 'provenance': {}}]}
        def fixture(manifest, files):
            module = json.loads(files['code/module.json'])
            module.update(host_min_version='8.12', enabled_tools=['nidus', 'glioma', 'metastasis', 'meningioma', 'anatomia'],
                          resource_recipe='catalog/resource_recipe.json')
            files['code/module.json'] = external._json(module)
            files['code/catalog/resource_recipe.json'] = external._json(recipe)
            catalog = {'schema': 'neuro-rt/catalog/1', 'models': [{'id': 'fixture-model', 'revision': '1',
                'catalog_state': 'distributed', 'groups': ['glioma'], 'channels': [{'role': 'T1c'}],
                'classes': [{'class_id': 'fixture'}], 'artifacts': [{'path': 'weights.bin', 'sha256': downloads['weight']['sha256']}],
                'license': {'code': 'MIT', 'weights': 'MIT', 'sources': ['https://example.invalid/license']}}]}
            files['code/catalog/models.json'] = external._json(catalog)
        package = host_setup(self.root, '1.1.0', mutate=fixture)
        source = self.root / 'progress-source'
        with zipfile.ZipFile(package['path']) as archive:
            archive.extractall(source)
            inventory = json.loads(archive.read('release-manifest.json'))
        model = source / 'models/fixture-model/1'; model.mkdir(parents=True)
        (model / 'weights.bin').write_bytes(weight)
        (model / 'LICENSE.txt').write_bytes(license_text)
        def prepare(actual_recipe, **kwargs):
            progress = kwargs['progress']
            for stage in ('checking', 'extracting'):
                progress({'stage': stage, 'label': 'fixture-model', 'completed_files': 1, 'total_files': 2})
            progress({'stage': 'preparing', 'label': wheel['name']})
            progress({'stage': 'unsafe-stage', 'label': 'C:/study/private.dcm',
                      'downloaded_bytes': -1, 'total_bytes': True, 'study_path': 'NEVER FORWARD'})
            for stage, label in (([], {}), ({}, []), (7, 'fixture-model'), ('checking', [])):
                progress({'stage': stage, 'label': label})
            return resource_preparation.prepare_resources(actual_recipe, **kwargs)
        for mode in ('local', 'online'):
            with self.subTest(mode=mode):
                host = self.root / ('host-' + mode); host.mkdir()
                for name in ('radai_panel.py', 'radai_ui.py', 'entrega.txt'):
                    (host / name).write_text('VERSAO=8.12\n')
                with patch.object(external, 'TRUSTED_CODE_INVENTORIES', {external.code_inventory_sha256(inventory)}):
                    if mode == 'local':
                        plan = external.prepare_external_plan({'mode': mode, 'local_source_accepted': True}, source_folder=source)
                    else:
                        plan = external.prepare_external_plan({'mode': mode, 'release': {'state': 'available',
                            'package_kind': 'setup', 'version': '1.1.0', 'release_id': 23, 'asset_id': 7,
                            'name': 'NEURO_RT_SETUP_v1.1.0.zip', 'size': Path(package['path']).stat().st_size,
                            'sha256': package['sha256'], 'url': 'https://api.github.com/repos/drhenriquebraga/neuro-rt/releases/assets/7'}})
                    events = []
                    def fetch(request, **kwargs):
                        return io.BytesIO(weight if request.full_url.endswith('/weights.bin') else license_text)
                    with patch('importlib.metadata.version', return_value='1.0'), \
                            patch.object(external, '_prepare_resources', side_effect=prepare), \
                            patch.object(resource_preparation, '_base_versions', return_value={resource_preparation._normal_name(wheel['name']): wheel['version']}), \
                            patch.object(plugin_update.ReleaseClient, 'download', return_value=package), \
                            patch('urllib.request.urlopen', side_effect=fetch) as network:
                        result = external.run_external(plan, events.append, suite_root=host, host_python=sys.executable)
                self.assertEqual(result['state'], 'ready')
                stages = {event.get('resource_stage') for event in events if event['stage'] == 'resources'}
                self.assertTrue({'checking', 'preparing', 'extracting', 'validating', 'complete'}.issubset(stages))
                self.assertTrue(any(event.get('component') == 'fixture-model' for event in events))
                self.assertTrue(any(event.get('component') == wheel['name'] for event in events))
                self.assertTrue(any(event.get('completed_files') == 1 and event.get('total_files') == 2 for event in events))
                self.assertFalse(any('study_path' in event or event.get('component') == 'C:/study/private.dcm' for event in events))
                self.assertFalse(any(event.get('resource_stage') == 'unsafe-stage' or event.get('downloaded_bytes') == -1
                                     or event.get('total_bytes') is True for event in events))
                if mode == 'local': network.assert_not_called()
                else:
                    self.assertIn('downloading', stages)
                    self.assertTrue(any(event.get('component') == 'weights.bin' and event.get('downloaded_bytes') == len(weight) for event in events))


if __name__ == '__main__':
    unittest.main()

"""Guided setup exports only pinned code/resources, never the base Python."""
import hashlib
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from host_setup_fixtures import host_setup
from neuro_rt import external_install, install_state, plugin_consent, setup_wizard as wizard


class SetupWizardTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / 'runtime/test-tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.wheel = b'invented wheel archive fixture'
        self.reused_wheel = b'invented archive already available in source base'
        self.extra = b'# invented extra fixture\n'
        self.weight = b'invented nonclinical weight fixture'
        self.license = b'Synthetic MIT attribution'
        def record(raw): return {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        self.recipe = {'schema': 'neuro-rt/resource-recipe/1', 'protected_base': {}, 'downloads': {},
            'wheels': [dict(name='fixture-extra', filename='fixture.whl', url='https://example.org/fixture.whl', **record(self.wheel)),
                       dict(name='reused-extra', filename='reused.whl', url='https://example.org/reused.whl', **record(self.reused_wheel))], 'adapters': {},
            'models': [{'id': 'fixture-model', 'revision': '1', 'provenance': {},
                        'files': {'weights.onnx': record(self.weight), 'LICENSE.txt': record(self.license)}}]}
        def mutate(manifest, files):
            files['code/catalog/resource_recipe.json'] = external_install._json(self.recipe)
            catalog = json.loads(files['code/catalog/models.json'])
            model = catalog['models'][0]
            model.update(id='fixture-model', revision='1', catalog_state='distributed',
                         classes=[{'class_id': 'fixture'}], artifacts=[dict(path='weights.onnx', **record(self.weight))])
            files['code/catalog/models.json'] = json.dumps(catalog).encode()
        package = host_setup(self.root, '1.1.0', mutate=mutate)
        self.source = self.root / 'setup'
        with zipfile.ZipFile(package['path']) as archive: archive.extractall(self.source)
        manifest = json.loads((self.source / 'release-manifest.json').read_text())
        pin = external_install.code_inventory_sha256(manifest)
        pins = patch.object(external_install, 'TRUSTED_CODE_INVENTORIES', {pin})
        pins.start(); self.addCleanup(pins.stop)
        self.cache = self.root / 'cache'
        self.output = self.root / 'offline'
        policy = plugin_consent.policy()
        self.terms = dict(accepted=True, version=policy['version'], digest=policy['digest'])

    def resources(self, recipe, *, plugin_root, **kwargs):
        if kwargs.get('progress'):
            kwargs['progress']({'stage': 'downloading', 'label': 'fixture-model',
                                'downloaded_bytes': 5, 'total_bytes': 10, 'study_path': 'NEVER FORWARD'})
            kwargs['progress']({'stage': [], 'label': {}, 'downloaded_bytes': True})
            kwargs['progress']({'stage': 'preparing', 'label': recipe['wheels'][0]['name']})
        recipe_sha = hashlib.sha256(external_install._json(recipe)).hexdigest()
        extras = 'extras/' + 'a'*64 + '/site-packages'
        values = {'schema': 'neuro-rt/resolved-resources/1', 'recipe_digest': recipe_sha,
                  'extras_digest': 'a'*64, 'extras_relative_path': extras,
                  'model_relative_paths': {'fixture-model': 'models/fixture-model/1'}, 'capabilities': {}}
        files = {extras + '/fixture/__init__.py': self.extra,
                 'models/fixture-model/1/weights.onnx': self.weight,
                 'models/fixture-model/1/LICENSE.txt': self.license,
                 'models/fixture-model/1/provenance.json': b'{}\n',
                 'cache/resources/downloads/' + hashlib.sha256(self.wheel).hexdigest() + '/fixture.whl': self.wheel,
                 'python/python.exe': b'NEVER COPY BASE OR CACHE CONTENTS BY TREE',
                 'data/private.dcm': b'synthetic excluded bait'}
        for name, raw in files.items():
            path = plugin_root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        receipt = dict(values, wheels=recipe['wheels'][:1], extra_file_inventory={
            'fixture/__init__.py': {'size': len(self.extra), 'sha256': hashlib.sha256(self.extra).hexdigest()}})
        relative = 'resources/' + recipe_sha + '.json'
        target = plugin_root / relative; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(external_install._json(receipt))
        return dict(values, receipt_relative_path=relative, receipt_sha256=hashlib.sha256(target.read_bytes()).hexdigest())

    def archives(self, recipe, *, plugin_root, **kwargs):
        for spec, raw in zip(recipe['wheels'], (self.wheel, self.reused_wheel)):
            target = plugin_root / ('cache/resources/downloads/' + spec['sha256'] + '/' + spec['filename'])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        return recipe['wheels']

    def test_offline_bundle_has_code_models_extra_archives_and_licenses_without_python(self):
        events = []
        with patch.object(wizard, '_prepare_resources', side_effect=self.resources), \
                patch.object(wizard, '_prepare_offline_archives', side_effect=self.archives, create=True):
            result = wizard.build_local_bundle(self.output, source_folder=self.source,
                cache_root=self.cache, host_python=sys.executable, terms=self.terms, progress=events.append)
        self.assertEqual(result['state'], 'ready')
        self.assertEqual((self.output / ('downloads/' + hashlib.sha256(self.wheel).hexdigest() + '/fixture.whl')).read_bytes(), self.wheel)
        self.assertEqual((self.output / ('downloads/' + hashlib.sha256(self.reused_wheel).hexdigest() + '/reused.whl')).read_bytes(), self.reused_wheel)
        self.assertEqual((self.output / 'models/fixture-model/1/weights.onnx').read_bytes(), self.weight)
        self.assertEqual((self.output / 'models/fixture-model/1/LICENSE.txt').read_bytes(), self.license)
        self.assertFalse((self.output / 'extras').exists(), 'Transport wheels once, not a duplicate expanded overlay')
        transport = json.loads((self.output / 'offline-bundle.json').read_text())
        self.assertNotIn('resources', transport)
        self.assertEqual(transport['categories']['wheels']['files'], 2)
        self.assertFalse(transport['resources_resolved_for_target'])
        self.assertTrue(any(event.get('downloaded_bytes') == 5 and event.get('component') == 'fixture-model' for event in events))
        self.assertTrue(any(event.get('component') == 'fixture-extra' for event in events))
        self.assertTrue(any(event.get('stage') == 'copying' and event.get('processed_bytes', 0) > 0 for event in events))
        self.assertFalse(any('study_path' in event for event in events))
        self.assertEqual(external_install.inspect_local_source(self.output)['version'], '1.1.0')
        names = {p.relative_to(self.output).as_posix() for p in self.output.rglob('*') if p.is_file()}
        self.assertFalse(any('python' in p.lower() or '.venv' in p or 'private.dcm' in p for p in names))

    def test_cancel_and_partial_resources_do_not_publish_bundle(self):
        with self.assertRaises(install_state.InstallFailure):
            wizard.build_local_bundle(self.output, source_folder=self.source,
                cache_root=self.cache, host_python=sys.executable, terms=self.terms, progress=lambda _: False)
        self.assertFalse(self.output.exists())
        with patch.object(wizard, '_prepare_resources', side_effect=OSError('synthetic partial')):
            with self.assertRaises(OSError):
                wizard.build_local_bundle(self.output, source_folder=self.source,
                    cache_root=self.cache, host_python=sys.executable, terms=self.terms)
        self.assertFalse(self.output.exists())

    def test_missing_preparation_terms_cannot_start_resource_downloads_or_record_installation(self):
        with patch.object(wizard, '_prepare_resources', side_effect=AssertionError('No download before terms')):
            with self.assertRaises(ValueError):
                wizard.build_local_bundle(self.output, source_folder=self.source,
                    cache_root=self.cache, host_python=sys.executable)
        self.assertFalse(self.cache.exists())

    def test_prepare_opens_only_the_host_owned_settings_entrypoint(self):
        host = self.root / 'host'; host.mkdir()
        entry = host / 'radai_plugin_setup.py'; entry.write_text('# trusted host fixture')
        with patch.object(wizard.subprocess, 'run') as run:
            wizard.open_host_settings(host, host_python=sys.executable)
        self.assertEqual(run.call_args.args[0], [str(Path(sys.executable).resolve()), '-I', '-B',
            str(entry.resolve()), '--open-settings', '--suite-root', str(host.resolve())])

    def test_describe_is_json_only_and_does_not_prepare_or_record_consent(self):
        host = self.root / 'suite'; host.mkdir()
        for name in ('radai_panel.py', 'radai_ui.py', 'entrega.txt'):
            (host / name).write_text('VERSAO=8.12\n')
        output = io.StringIO()
        with patch('importlib.metadata.version', return_value='1.0'), \
                patch.object(wizard, '_prepare_resources', side_effect=AssertionError('Describe must not download')), \
                contextlib.redirect_stdout(output):
            result = wizard.main(['--suite-root', str(host), '--describe'])
        self.assertEqual(result, 0)
        description = json.loads(output.getvalue())
        self.assertEqual(description['policy']['digest'], self.terms['digest'])
        self.assertTrue(description['licenses'].strip())
        self.assertFalse((host / 'Plugins').exists())

    def test_progress_file_is_bounded_metadata_and_cancel_is_cooperative(self):
        progress = self.root / 'progress.json'
        cancel = self.root / 'cancel.flag'
        report = wizard._progress_reporter(progress, cancel, quiet=True)
        self.assertTrue(report({'state': 'preparing', 'stage': 'resources', 'resource_stage': 'downloading',
                                'component': 'fixture-model', 'downloaded_bytes': 5, 'total_bytes': 10,
                                'study_path': 'NEVER FORWARD'}))
        value = json.loads(progress.read_text())
        self.assertNotIn('study_path', value)
        self.assertEqual(value['downloaded_bytes'], 5)
        cancel.write_text('cancel')
        self.assertFalse(report({'state': 'preparing', 'stage': 'resources'}))


if __name__ == '__main__': unittest.main()

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from scripts import build_plugin_release as builder
from neuro_rt import install_state
from test_plugin_install import fixture_package


class ReleaseBuilderTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.research/test_plugin_tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        package = fixture_package(self.root)
        with zipfile.ZipFile(package['path']) as archive:
            archive.extractall(self.root / 'input')
        self.source = self.root / 'input/code'
        self.runtime = next((self.root / 'input/runtimes/fixture-cpu').iterdir())
        self.lock = self.root / 'lock.txt'
        self.lock.write_text('synthetic==1.0\n')
        self.spec = {'fixture-cpu': {'path': self.runtime, 'lock': self.lock,
                                    'python': 'python.exe', 'license_paths': ['LICENSE.txt']}}
        (self.source / 'scripts').mkdir()
        (self.source / 'scripts/model_assets_v1_manifest.json').write_text(json.dumps({'models': {'fixture': {
            'files': {'model.onnx': {'size': len(b'synthetic weight'),
                'sha256': hashlib.sha256(b'synthetic weight').hexdigest()}}}}}))

    def build(self):
        return builder.build_release('1.0.0', self.source / 'catalog/models.json', self.spec,
            self.root / 'output', root=self.source, models_dir=self.root / 'input/models')

    def test_release_can_be_installed_and_manifest_matches_every_byte(self):
        artifacts = self.build()
        result = builder.verify_release(artifacts.manifest, artifacts.offline)
        self.assertTrue(result['ok'])
        with zipfile.ZipFile(artifacts.offline) as archive:
            manifest = json.loads(archive.read('release-manifest.json'))
            self.assertEqual({r['path'] for r in manifest['files']}, set(archive.namelist()) - {'release-manifest.json'})
        self.assertEqual(artifacts.offline.read_bytes(), self.build().offline.read_bytes())
        host = self.root / 'host sintético'
        host.mkdir()
        for name in ('radai_panel.py', 'radai_ui.py', 'entrega.txt'):
            (host / name).write_text('synthetic host')
        receipt = install_state.begin_install(host, {'path': str(artifacts.offline),
            'sha256': hashlib.sha256(artifacts.offline.read_bytes()).hexdigest()}, 'built-release')
        self.assertTrue(receipt.activation_pending)
        self.assertEqual(install_state.activate_release(host / 'Plugins/NEURO RT', receipt.version).active_version, '1.0.0')
        from neuro_rt.adapters import _scientific
        from types import SimpleNamespace
        from unittest.mock import patch
        installed_code = host / 'Plugins/NEURO RT/versions/1.0.0'
        self.assertFalse((installed_code / 'scripts').exists())
        context = SimpleNamespace(model_spec={'id': 'fixture', 'revision': '1'},
            models_dir=host / 'Plugins/NEURO RT/models', allow_legacy_models=False)
        with patch.object(_scientific, '__file__', str(installed_code / 'neuro_rt/adapters/_scientific.py')):
            folder, hashes = _scientific.verified_assets(context)
        self.assertEqual(folder, host / 'Plugins/NEURO RT/models/fixture/1')
        self.assertIn('model.onnx', hashes)

    def test_data_named_like_atlas_is_excluded_and_unlicensed_component_rejected(self):
        (self.source / 'data').mkdir()
        (self.source / 'data/atlas_labels.nii').write_bytes(b'patient bait')
        artifacts = self.build()
        with zipfile.ZipFile(artifacts.offline) as archive:
            self.assertFalse(any('patient' in n or n.endswith('.nii') for n in archive.namelist()))
        (self.runtime / 'LICENSE.txt').unlink()
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.build()

    def test_atlas_name_without_exact_public_identity_is_rejected(self):
        model = self.root / 'input/models/fixture/1'
        (model / 'atlas_labels.nii').write_bytes(b'patient bait')
        catalog = json.loads((self.source / 'catalog/models.json').read_text())
        catalog['models'][0]['artifacts'].append({'path': 'atlas_labels.nii',
            'sha256': hashlib.sha256(b'patient bait').hexdigest()})
        (self.source / 'catalog/models.json').write_text(json.dumps(catalog))
        with self.assertRaisesRegex(ValueError, 'atlas'):
            self.build()

    def test_optional_host_buti_never_duplicates_host_runtime_or_weights(self):
        import copy
        catalog = json.loads((self.source / 'catalog/models.json').read_text())
        model = copy.deepcopy(catalog['models'][0])
        model.update(id='cranio_buti', runtime_id='host-nnunet', adapter_id='buti_host', host_managed=True)
        catalog['models'].append(model)
        (self.source / 'catalog/models.json').write_text(json.dumps(catalog))
        artifacts = self.build()
        with zipfile.ZipFile(artifacts.offline) as archive:
            manifest = json.loads(archive.read('release-manifest.json'))
            self.assertNotIn('host-nnunet', [r['id'] for r in manifest['runtimes']])
            self.assertNotIn('cranio_buti', [r['id'] for r in manifest['models']])

    def test_refresh_code_reuses_verified_component_bytes_without_source_runtime(self):
        artifacts = self.build()
        original = json.loads(artifacts.manifest.read_text())
        (self.source / 'neuro_rt').mkdir()
        (self.source / 'neuro_rt/new_feature.py').write_bytes(b'VALUE = 42\n')
        refreshed = builder.refresh_code_release(artifacts.offline, artifacts.manifest,
            root=self.source, output_dir=self.root / 'refreshed')
        after = json.loads(refreshed.manifest.read_text())
        self.assertEqual([r for r in original['files'] if not r['path'].startswith('code/')],
                         [r for r in after['files'] if not r['path'].startswith('code/')])
        with zipfile.ZipFile(refreshed.offline) as archive:
            self.assertEqual(archive.read('code/neuro_rt/new_feature.py'), b'VALUE = 42\n')
        self.assertTrue(builder.verify_release(refreshed.manifest, refreshed.offline)['ok'])

    def test_manifest_capacity_accepts_realistic_large_inventory_but_stays_bounded(self):
        import base64
        import random
        padding = base64.b64encode(random.Random(1729).randbytes(13 * 1024 * 1024)).decode('ascii')
        accepted = fixture_package(self.root, '3.0.0', mutate=lambda manifest, files:
            manifest.update(build_inventory_notes=padding[:9 * 1024 * 1024]))
        with zipfile.ZipFile(accepted['path']) as archive:
            size = archive.getinfo('release-manifest.json').file_size
            self.assertGreater(size, 8 * 1024 * 1024)
            self.assertLess(size, 16 * 1024 * 1024)
            self.assertEqual(install_state._inspect_zip(archive)[0]['version'], '3.0.0')
        oversized = fixture_package(self.root, '4.0.0', mutate=lambda manifest, files:
            manifest.update(build_inventory_notes=padding))
        with zipfile.ZipFile(oversized['path']) as archive:
            self.assertGreater(archive.getinfo('release-manifest.json').file_size, 16 * 1024 * 1024)
            with self.assertRaises(ValueError):
                install_state._inspect_zip(archive)

    def test_license_prefix_never_admits_images_or_binary_disguised_as_text(self):
        model = self.root / 'input/models/fixture/1'
        for name in ('LICENSE_patient.nii.gz', 'NOTICE_patient.dcm', 'COPYING_patient.dicom'):
            (model / name).write_bytes(b'synthetic image bait')
        (model / 'LICENSE_binary.txt').write_bytes(b'DICM\x00synthetic binary bait')
        (model / 'LICENSE.extra.html').write_text('<html>Synthetic original MIT notice</html>', encoding='utf-8')
        samples = self.runtime / 'Lib/site-packages/synthetic/tests'
        samples.mkdir(parents=True)
        for name in ('DICOMDIR', 'sample.dcm.gz', 'sample.ima.gz'):
            (samples / name).write_bytes(b'synthetic wheel sample')
        artifacts = self.build()
        with zipfile.ZipFile(artifacts.offline) as archive:
            names = archive.namelist()
            self.assertFalse(any('patient' in name or 'LICENSE_binary' in name for name in names))
            self.assertFalse(any(name.endswith(('DICOMDIR', '.dcm.gz', '.ima.gz')) for name in names))
            self.assertIn('models/fixture/1/LICENSE.extra.html', names)

    def test_verify_and_refresh_reject_images_in_final_inventory_even_as_license(self):
        for filename, error in [('NOTICE_patient.dcm', 'DICOM'), ('LICENSE_patient.nii.gz', 'atlas')]:
            with self.subTest(filename=filename):
                def mutate(manifest, files):
                    name = 'models/fixture/1/' + filename
                    raw = b'synthetic medical-image bait'
                    files[name] = raw
                    manifest['files'].append({'path': name, 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
                    manifest['models'][0]['license_paths'].append(filename)
                package = fixture_package(self.root, '1.0.0', mutate=mutate)
                manifest = self.root / 'bad-manifest.json'
                with zipfile.ZipFile(package['path']) as archive:
                    manifest.write_bytes(archive.read('release-manifest.json'))
                with self.assertRaisesRegex(ValueError, error):
                    builder.verify_release(manifest, package['path'])
                with self.assertRaisesRegex(ValueError, error):
                    builder.refresh_code_release(package['path'], manifest, root=self.source, output_dir=self.root / 'refused')

    def test_final_policy_accepts_exact_public_atlas_records_and_rejects_changed_identity(self):
        import copy
        atlas = json.loads((Path(__file__).resolve().parents[1] / 'catalog/atlas_assets.json').read_text())
        records = [{'path': 'models/' + atlas['model_id'] + '/cerebra-mni2009c-sym-v1/' + item['path'].split('/', 1)[1],
                    'size': item['size'], 'sha256': item['sha256']}
                   for item in atlas['allowlist'] if item.get('format') == 'nifti']
        data = {'files': records}
        builder.validate_image_inventory(data, atlas)
        wrong = copy.deepcopy(data)
        wrong['files'][0]['sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'atlas'):
            builder.validate_image_inventory(wrong, atlas)

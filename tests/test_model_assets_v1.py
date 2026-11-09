"""Integrity and archive boundary tests; no network or clinical data."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location(
    'model_assets_v1', Path(__file__).resolve().parents[1] / 'scripts/model_assets_v1.py')
assets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assets)


class ModelAssetsV1Tests(unittest.TestCase):
    def test_rejects_html_even_when_hash_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'weights.pth'
            path.write_bytes(b'<!doctype html><title>download failed</title>')
            with self.assertRaisesRegex(ValueError, 'HTML'):
                assets.verify_file(path, hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size, 'torch')

    def test_rejects_wrong_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'weights.pth'
            path.write_bytes(b'PK\x03\x04binary')
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                assets.verify_file(path, '0' * 64, path.stat().st_size, 'torch')

    def test_rejects_zip_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'archive.zip'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('../escape', b'unsafe')
            with self.assertRaisesRegex(ValueError, 'ZIP'):
                assets.extract_allowed(path, Path(tmp) / 'dest', {'../escape': 'file'})
            self.assertFalse((Path(tmp) / 'escape').exists())

    def test_extracts_only_allowlisted_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'archive.zip'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('public/atlas.nii', b'atlas')
                z.writestr('unselected.nii', b'excluded')
            dest = Path(tmp) / 'dest'
            assets.extract_allowed(path, dest, {'public/atlas.nii': 'atlas.nii'})
            self.assertEqual((dest / 'atlas.nii').read_bytes(), b'atlas')
            self.assertFalse((dest / 'unselected.nii').exists())

    def test_every_asset_pins_integrity_and_origin(self):
        for name, entry in assets.MANIFEST['downloads'].items():
            with self.subTest(asset=name):
                self.assertEqual(len(entry['sha256']), 64)
                self.assertGreater(entry['size'], 0)
                self.assertTrue(entry['url'].startswith('https://'))

    def test_valid_cache_never_opens_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'weights.pth'
            path.write_bytes(b'PK\x03\x04binary')
            entry = {'filename': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'size': path.stat().st_size, 'format': 'torch', 'url': 'https://example.test/weights'}
            with patch.object(assets.urllib.request, 'urlopen') as network:
                self.assertEqual(assets.fetch(entry, Path(tmp)), path)
            network.assert_not_called()

    def test_missing_license_is_incomplete_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / 'test_model'
            model.mkdir()
            (model / 'weight').write_bytes(b'PK\x03\x04binary')
            spec = {'files': {'LICENSE.weights.txt': {'sha256': '0' * 64, 'size': 10, 'format': 'text'}}}
            with patch.dict(assets.MANIFEST['models'], {'test_model': spec}):
                with self.assertRaises(FileNotFoundError):
                    assets.verify_model('test_model', Path(tmp))


if __name__ == '__main__':
    unittest.main()

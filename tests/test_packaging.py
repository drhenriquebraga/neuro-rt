import tempfile
import unittest
from pathlib import Path

from scripts.package_module import source_files, SOURCE_FILES
from scripts.prepare_models import install_archive
from neuro_rt.catalog import get_model
from test_pipeline import TEMP_ROOT


class PackagingTests(unittest.TestCase):
    def test_sources_include_catalog_and_migrated_nidus(self):
        root = Path(__file__).resolve().parents[1]
        names = {file.relative_to(root).as_posix() for file in source_files(root)}
        for required in ('catalog/models.json', 'app/radai_nidus.py',
                         'app/radai_nidus_screen.py', 'tools/test_nidus.py',
                         'licenses/NIDUS_RT_APACHE_2.txt'):
            self.assertIn(required, names)

    def test_sources_exclude_private_config_and_jobs(self):
        root = Path(__file__).resolve().parents[1]
        files = source_files(root)
        names = [file.relative_to(root).as_posix() for file in files]
        self.assertIn('licenses/RAIDIONICS_MODELS.txt', names)
        self.assertIn('licenses/RAIDIONICS_ENGINE.txt', names)
        self.assertNotIn('neuro_rt.local.json', names)
        self.assertFalse(any(name.startswith(('runtime/','.venv/','.research/','python/')) for name in names))

    def test_incomplete_archive_does_not_become_ready(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            file = Path(tmp) / 'invalid.zip'
            file.write_bytes(b'incomplete')
            with self.assertRaises(ValueError):
                install_archive(file,get_model('MRI_GBM'),Path(tmp)/'models')
            self.assertFalse((Path(tmp)/'models/MRI_GBM').exists())


if __name__ == '__main__':
    unittest.main()

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from synthetic_dicom import make_series
from test_pipeline import TEMP_ROOT


class HostBindingsTests(unittest.TestCase):
    def test_real_host_ticket_owner_supplies_private_source_and_scoped_identity(self):
        from integration.host_imports import prepare_host_imports
        from integration.default_host_services import bindings_for_host
        prepare_host_imports(Path('C:/AI_PROJETOS/AUTO_CONTORNO'))
        import radai_dicom
        import radai_thumbnail
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            folder = Path(tmp)
            uid, _ = make_series(folder)
            series = radai_dicom.varrer(str(folder))['series']
            ticket = radai_thumbnail.registrar_series(str(folder), series)[uid]
            bindings = bindings_for_host({'suite_root': 'unused'})
            value = bindings['resolve_series_ticket'](ticket)
            self.assertEqual(value['ticket'], ticket)
            self.assertEqual(value['series_uid'], uid)
            self.assertEqual(len(value['source']['dicom_files']), 8)
            self.assertNotIn('SYNTHETIC', value['subject_key'])
            self.assertEqual(value['subject_key'], bindings['resolve_series_ticket'](ticket)['subject_key'])
            with self.assertRaises(ValueError): bindings['resolve_series_ticket']('../private')

    def test_device_preference_uses_existing_station_configuration(self):
        from integration.host_imports import prepare_host_imports
        from integration.default_host_services import bindings_for_host
        prepare_host_imports(Path('C:/AI_PROJETOS/AUTO_CONTORNO'))
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            path = Path(tmp) / 'station.config'
            bindings = bindings_for_host({}, {'caminho': str(path)})
            path.write_text('DEVICE=cpu\n')
            self.assertEqual(bindings['device_preference'](), 'cpu')
            path.write_text('DEVICE=gpu\n')
            self.assertEqual(bindings['device_preference'](), 'cuda')

    def test_published_result_delegates_to_existing_archive(self):
        from integration.default_host_services import bindings_for_host
        calls = []
        fake = SimpleNamespace(registrar_serie=lambda *a, **kw: calls.append((a, kw)) or True)
        bindings = bindings_for_host({})
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp, patch.dict(sys.modules, {'radai_archive': fake}):
            published = Path(tmp) / 'RS_test.dcm'; published.write_bytes(b'synthetic')
            bindings['register_result']({'manifest': {'reference': {'series_uid': '1.2'},
                'plugin_version': 'test', 'export_status': 'completed', 'export_receipt': {
                    'published_file': str(published), 'delivered_rois': ['one', 'two']}}})
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]['estruturas'], 2)

    def test_incomplete_retry_does_not_replace_valid_archive_publication(self):
        from integration.default_host_services import bindings_for_host
        archive = {}
        def register(uid, folder, filename, **kwargs):
            archive[uid] = str(Path(folder) / filename)
            return True
        bindings = bindings_for_host({})
        fake = SimpleNamespace(registrar_serie=register)
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp, patch.dict(sys.modules, {'radai_archive': fake}):
            published = Path(tmp) / 'RS_valid.dcm'; published.write_bytes(b'synthetic')
            manifest = {'reference': {'series_uid': '1.2'}, 'plugin_version': 'test',
                'export_status': 'completed', 'export_receipt': {'published_file': str(published), 'delivered_rois': ['one']}}
            bindings['register_result']({'manifest': manifest})
            for status, path in (('incomplete', ''), ('failed', ''), ('pending', str(published)),
                                 ('completed', ''), ('completed', 'relative.dcm'),
                                 ('completed', str(Path(tmp) / 'missing.dcm')), ('completed', str(Path(tmp)))):
                with self.subTest(status=status, path=path):
                    retry = {**manifest, 'export_status': status, 'export_receipt': {
                        'published_file': path, 'delivered_rois': ['one']}}
                    bindings['register_result']({'manifest': retry})
                    self.assertEqual(archive, {'1.2': str(published)})

"""TOF suggestions use invented headers only and never choose/import a series."""
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage, generate_uid

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/radai_nidus_screen.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf8'))
FUNCTIONS = ('_classificar_tof', '_cabecalhos_tof', '_sugestoes_tof')
NAMESPACE = {'hashlib': hashlib, 'os': os}
exec(compile(ast.Module(body=[node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS], type_ignores=[]), str(SOURCE), 'exec'), NAMESPACE)
classify, headers, suggest = [NAMESPACE[name] for name in FUNCTIONS]


def write_series(folder, name, description, *, patient='SYNTHETIC_A', study=None,
                 acquisition='3D', image_type=('ORIGINAL', 'PRIMARY'), modality='MR'):
    folder.mkdir(parents=True, exist_ok=True)
    uid = generate_uid()
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = MRImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    ds = FileDataset(str(folder / name), {}, file_meta=meta, preamble=bytes(128))
    ds.SOPClassUID = MRImageStorage
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.SeriesInstanceUID = uid
    ds.StudyInstanceUID = study or generate_uid()
    ds.PatientID = patient
    ds.Modality = modality
    ds.SeriesDescription = description
    ds.ProtocolName = 'SYNTHETIC MRA'
    ds.SequenceName = '*TOF3D' if 'TOF' in description else '*t1'
    ds.MRAcquisitionType = acquisition
    ds.ImageType = list(image_type)
    ds.save_as(folder / name, enforce_file_format=True)
    return str(folder), uid


class TofMetadata(unittest.TestCase):
    def test_vendor_name_is_only_a_possible_tof_not_a_certain_identity(self):
        value = classify({'Modality':'MR','SeriesDescription':'AXI3DTOF3SLABFSMTASSET'})
        self.assertTrue(value['possivel_tof'])
        self.assertTrue(value['tridimensional'])
        self.assertFalse(value['original'])
        self.assertNotIn('certainty', value)
        for metadata in ({'Modality':'CT','SeriesDescription':'3D TOF'},
                         {'Modality':'MR','ProtocolName':'MRA','MRAcquisitionType':'3D'},
                         {'Modality':'MR','SeriesDescription':'STOF test'}):
            self.assertFalse(classify(metadata)['possivel_tof'])

    def test_source_original_is_preferred_and_mip_or_derived_are_excluded(self):
        original = classify({'Modality':'MR','ProtocolName':'3D TOF','ImageType':['ORIGINAL','PRIMARY']})
        unknown = classify({'Modality':'MR','SequenceName':'3DTOF'})
        self.assertGreater(original['prioridade'], unknown['prioridade'])
        for changes in ({'ImageType':['DERIVED','SECONDARY']}, {'SeriesDescription':'3D TOF MIP'}, {'ImageType':['MIP']}):
            value = classify({'Modality':'MR','ProtocolName':'3D TOF', **changes})
            self.assertFalse(value['possivel_tof'])
            self.assertEqual(value['prioridade'], 0)

    def test_header_reader_stops_before_pixels_and_filters_series_uid(self):
        with tempfile.TemporaryDirectory(prefix='nidus-tof-synthetic-') as temp:
            folder = Path(temp)
            _, uid = write_series(folder, 'source.dcm', '3D TOF')
            write_series(folder, 'other.dcm', 'MIP')
            with patch.object(pydicom, 'dcmread', wraps=pydicom.dcmread) as read:
                result = headers(str(folder), [uid])
            self.assertEqual(set(result), {uid})
            self.assertTrue(all(call.kwargs['stop_before_pixels'] for call in read.call_args_list))
            self.assertTrue(all('PixelData' not in call.kwargs['specific_tags'] for call in read.call_args_list))

    def fixtures(self, folder):
        study = generate_uid()
        rows = {
            'reference':write_series(folder, 'reference.dcm', 'T1 reference', study=study),
            'source':write_series(folder, 'source.dcm', 'AXI3DTOF3SLABFSMTASSET', study=study),
            'mip':write_series(folder, 'mip.dcm', '3D TOF MIP', study=study, image_type=('DERIVED','SECONDARY')),
            'unknown':write_series(folder, 'unknown.dcm', '3D TOF', study=study, image_type=()),
            'other_patient':write_series(folder, 'patient.dcm', '3D TOF', study=study, patient='SYNTHETIC_B'),
            'other_study':write_series(folder, 'study.dcm', '3D TOF'),
        }
        return rows

    def test_anchor_cannot_suggest_another_patient_or_study_and_does_not_return_ids(self):
        with tempfile.TemporaryDirectory(prefix='nidus-tof-synthetic-') as temp:
            rows = self.fixtures(Path(temp))
            items = [{'bilhete':ticket,'origem':'pasta'} for ticket in rows]
            response = suggest(items, lambda ticket, origin:rows[ticket], {'bilhete':'reference','origem':'pasta'})
            preferred = [row['bilhete'] for row in response['itens'] if row['preferida']]
            self.assertEqual(preferred, ['source'])
            serialized = json.dumps(response)
            self.assertNotIn('SYNTHETIC_A', serialized)
            self.assertNotIn('PatientID', serialized)
            self.assertNotIn('StudyInstanceUID', serialized)
            self.assertNotIn('grupo', serialized)

    def test_unknown_anchor_or_missing_patient_study_produces_no_preference(self):
        with tempfile.TemporaryDirectory(prefix='nidus-tof-synthetic-') as temp:
            rows = self.fixtures(Path(temp))
            response = suggest([{'bilhete':'source'}], lambda ticket, origin:rows.get(ticket,(None,None)), {'bilhete':'unknown_ticket'})
            self.assertFalse(response['itens'][0]['preferida'])
        self.assertFalse(classify({'Modality':'MR','SeriesDescription':'3D TOF'})['grupo'])


class TofPickerBrowser(unittest.TestCase):
    def test_suggestions_keep_explicit_selection_and_never_auto_import(self):
        node = shutil.which('node')
        module = Path(os.environ.get('RADAI_PLAYWRIGHT_MODULE', str(Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')))
        chrome = Path(os.environ.get('RADAI_CHROME', r'C:\Program Files\Google\Chrome\Application\chrome.exe'))
        if not node or not module.is_dir() or not chrome.is_file():
            self.skipTest('Chrome/Playwright not installed')
        assignment = next(node for node in TREE.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id=='JS_TELA' for target in node.targets))
        source = ast.literal_eval(assignment.value)
        script = source[source.index('function ndRotuloDaLista(s)'):source.index('function ndRotuloDaSerie(t)')]
        with tempfile.TemporaryDirectory(prefix='nidus-tof-picker-') as temp:
            folder = Path(temp)
            (folder/'picker.js').write_text(script, encoding='utf8')
            result = subprocess.run([node,str(ROOT/'tests/nidus_tof_picker_browser.cjs'),str(folder),str(module),str(chrome)], capture_output=True,text=True,encoding='utf8',errors='replace',timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('PASS',result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pydicom
import SimpleITK as sitk

from neuro_rt.imaging import geometry, load_input
from neuro_rt.study_types import MaskArtifact, ModelResult, SeriesDescriptor, StudyManifest
from synthetic_dicom import make_series
from test_pipeline import TEMP_ROOT

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT.parent / 'AUTO_CONTORNO'


class StudyExportTests(unittest.TestCase):
    def prepare(self, job, tiny=False, empty=False, modality='MR',
                model_ids=('MRI_GBM', 'MRI_Meningioma')):
        uid, frame = make_series(job / 'original', modality=modality)
        shutil.copytree(job / 'original', job / 'dicom_source')
        image, source = load_input(job / 'original', uid, allowed_modalities=(modality,))
        source['input_path'] = str(job / 'original')
        (job / 'inputs').mkdir()
        sitk.WriteImage(image, str(job / 'inputs/reference.nii.gz'))
        (job / 'masks').mkdir()
        results = []
        for index, model in enumerate(model_ids):
            bits = np.zeros((8, 16, 16), dtype=np.uint8)
            if not empty:
                bits[2:5, 5:10, 7:11] = 1
                bits[2:5, 1:4, 1:4] = 1
            if tiny and index == 1:
                bits[:] = 0
                bits[2, 2, 2] = 1
            mask = sitk.GetImageFromArray(bits)
            mask.CopyInformation(image)
            relative = f'masks/model{index}.nii.gz'
            sitk.WriteImage(mask, str(job / relative))
            results.append(ModelResult(model, 'completed', [
                MaskArtifact(model, 'tumor', relative, geometry(image))],
                versions={'model': '1.2.0'}))
        manifest = StudyManifest('request', 'study', '0.3', 1,
            SeriesDescriptor('ticket', uid, 'subject', 'study', modality, geometry(image),
                             frame_of_reference_uid=frame,
                             sop_instance_uids=source['sop_uids']),
            [r.model_id for r in results], results, 'completed', 'cpu', 'cpu')
        (job / 'study-manifest.json').write_text(json.dumps(manifest.to_dict()))
        (job / 'source.json').write_text(json.dumps(source))
        return source

    def run_export(self, job, catalog=None, deny_publication=False, writer_fault=None,
                   capture_writer=False):
        config = ROOT / 'neuro_rt.local.json'
        if not config.is_file():
            self.skipTest('Runtime do host não configurado.')
        python = Path(json.loads(config.read_text())['host_python'])
        if not python.is_file() or not HOST.is_dir():
            self.skipTest('Runtime/gravador real indisponível.')
        bootstrap = ('import sys,runpy;sys.path.insert(0,sys.argv.pop(1));'
                     'runpy.run_module("neuro_rt.export_study",run_name="__main__")')
        if catalog is not None:
            bootstrap = ('import sys,json;sys.path.insert(0,sys.argv.pop(1));'
                         'from neuro_rt.export_study import export_study;'
                         'export_study(sys.argv[1],sys.argv[2],catalog=json.loads(sys.argv[3]))')
            return subprocess.run([str(python), '-c', bootstrap, str(ROOT), str(job),
                                   str(HOST), json.dumps(catalog)],
                                  cwd=ROOT, capture_output=True, timeout=120)
        if deny_publication:
            bootstrap = ('import sys,runpy\nfrom pathlib import Path\n'
                'sys.path.insert(0,sys.argv.pop(1))\noriginal_open=Path.open\n'
                'def restricted_open(path,*args,**kwargs):\n'
                ' if path.parent.name=="original" and args and args[0]=="xb":\n'
                '  raise PermissionError("synthetic publication denied")\n'
                ' return original_open(path,*args,**kwargs)\n'
                'Path.open=restricted_open\n'
                'runpy.run_module("neuro_rt.export_study",run_name="__main__")')
        if writer_fault is not None:
            bootstrap = ('import sys,runpy\nfrom pathlib import Path\n'
                'sys.path.insert(0,sys.argv.pop(1))\n'
                'from integration.host_imports import prepare_host_imports\n'
                'prepare_host_imports(sys.argv[sys.argv.index("--host-app")+1])\n'
                'import engine,pydicom\noriginal_build=engine.build_rtstruct\n'
                'def damaged(*args,**kwargs):\n'
                ' result=original_build(*args,**kwargs)\n'
                ' ds=pydicom.dcmread(result[0])\n'
                ' contour=ds.ROIContourSequence[0]\n'
                + {'focus': ' contour.ContourSequence=contour.ContourSequence[::2]\n',
                   'plane': ' contour.ContourSequence[0].ContourData[2]+=0.5\n',
                   'sop': ' contour.ContourSequence[0].ContourImageSequence[0].ReferencedSOPInstanceUID=contour.ContourSequence[-1].ContourImageSequence[0].ReferencedSOPInstanceUID\n'}[writer_fault]
                + ' ds.save_as(result[0],enforce_file_format=True)\n return result\n'
                'engine.build_rtstruct=damaged\n'
                'runpy.run_module("neuro_rt.export_study",run_name="__main__")')
        if capture_writer:
            bootstrap = ('import sys,shutil,json\nfrom pathlib import Path\n'
                'sys.path.insert(0,sys.argv.pop(1))\n'
                'job=Path(sys.argv[sys.argv.index("--job-dir")+1])\n'
                'host=sys.argv[sys.argv.index("--host-app")+1]\n'
                'from integration.host_imports import prepare_host_imports\n'
                'prepare_host_imports(host)\n'
                'import engine,pydicom,numpy as np\noriginal_build=engine.build_rtstruct\n'
                'def captured(*args,**kwargs):\n'
                ' result=original_build(*args,**kwargs)\n'
                ' shutil.copyfile(result[0],job/"writer-original.dcm")\n'
                ' return result\n'
                'engine.build_rtstruct=captured\n'
                'from neuro_rt.export_study import export_study\n'
                'receipt=export_study(job,host)\n'
                'from rt_utils import RTStructBuilder\nfrom radai_rt import SessaoRT\n'
                'ds=pydicom.dcmread(receipt.published_file)\n'
                'names=[str(roi.ROIName) for roi in ds.StructureSetROISequence]\n'
                'rt=RTStructBuilder.create_from(dicom_series_path=str(job/"dicom_source"),'
                'rt_struct_path=receipt.published_file)\n'
                'reader=SessaoRT(None,receipt.published_file,None,(8,16,16),names,rt)\n'
                'for name in names: np.save(job/("roundtrip_"+name+".npy"),reader.mascara(name))\n')
        return subprocess.run([str(python), '-c', bootstrap, str(ROOT),
                               '--job-dir', str(job), '--host-app', str(HOST)],
                              cwd=ROOT, capture_output=True, timeout=120)

    def test_same_class_two_models_one_file_all_foci_overlaps_and_retry(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            job = Path(tmp)
            source = self.prepare(job)
            run = self.run_export(job)
            self.assertEqual(run.returncode, 0, run.stderr.decode(errors='replace')[-1800:])
            result = json.loads((job / 'study-manifest.json').read_text())
            self.assertEqual(result['export_status'], 'completed')
            receipt = result['export_receipt']
            path = Path(receipt['published_file'])
            ds = pydicom.dcmread(path)
            self.assertEqual(ds.ApprovalStatus, 'UNAPPROVED')
            self.assertEqual(len(ds.StructureSetROISequence), 2)
            names = [str(roi.ROIName) for roi in ds.StructureSetROISequence]
            self.assertEqual(len(set(names)), 2)
            self.assertTrue(all(len(name) <= 16 and name.endswith('_ai') for name in names))
            for roi in ds.ROIContourSequence:
                points = np.concatenate([np.asarray(c.ContourData).reshape(-1, 3)
                                         for c in roi.ContourSequence])
                self.assertEqual(sorted(set(points[:, 2])), [4., 6., 8.])
                self.assertLess(points[:, 0].min(), 24.)
                self.assertGreater(points[:, 0].max(), 26.)
            self.assertEqual(len(list((job / 'original').glob('RS_NeuroRT_*.dcm'))), 1)
            original_bytes = path.read_bytes()
            self.assertEqual(self.run_export(job).returncode, 0)
            self.assertEqual(path.read_bytes(), original_bytes)
            self.assertEqual(len(list((job / 'original').glob('RS_NeuroRT_*.dcm'))), 2)
            self.assertEqual(set(source['sop_uids']), set(
                str(item.ReferencedSOPInstanceUID) for item in
                ds.ReferencedFrameOfReferenceSequence[0].RTReferencedStudySequence[0]
                  .RTReferencedSeriesSequence[0].ContourImageSequence))

    def test_export_colors_match_registry_preserve_writer_dataset_and_voxels(self):
        from neuro_rt.roi_registry import make_roi_identity
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            job = Path(tmp)
            source = self.prepare(job)
            run = self.run_export(job, capture_writer=True)
            self.assertEqual(run.returncode, 0, run.stderr.decode(errors='replace')[-1800:])
            result = json.loads((job / 'study-manifest.json').read_text())
            self.assertEqual(result['export_status'], 'completed')
            published = Path(result['export_receipt']['published_file'])
            ds = pydicom.dcmread(published)
            original = pydicom.dcmread(job / 'writer-original.dcm')
            names = {int(roi.ROINumber): str(roi.ROIName) for roi in ds.StructureSetROISequence}
            actual = {names[int(roi.ReferencedROINumber)]: tuple(int(c) for c in roi.ROIDisplayColor)
                      for roi in ds.ROIContourSequence}
            expected = {}
            for index, model in enumerate(('MRI_GBM', 'MRI_Meningioma')):
                identity = make_roi_identity(model, 'tumor', 1)
                expected[identity.roi_name] = identity.color
                restored = np.load(job / ('roundtrip_' + identity.roi_name + '.npy'))
                mask = sitk.GetArrayFromImage(sitk.ReadImage(str(job / f'masks/model{index}.nii.gz')))
                np.testing.assert_array_equal(restored, mask.astype(bool))
            self.assertEqual(actual, expected)
            # Exactly this presentation attribute may change after the host
            # writer. Compare every other DICOM element, including descriptions,
            # names, point coordinates, SOP/frame references and file metadata.
            for dataset in (original, ds):
                for roi in dataset.ROIContourSequence:
                    del roi.ROIDisplayColor
            self.assertEqual(original.file_meta, ds.file_meta)
            self.assertEqual(original, ds)
            self.assertEqual(str(ds.ApprovalStatus), 'UNAPPROVED')
            reference = ds.ReferencedFrameOfReferenceSequence[0]
            self.assertEqual(str(reference.FrameOfReferenceUID), source['frame_uid'])
            series = reference.RTReferencedStudySequence[0].RTReferencedSeriesSequence[0]
            self.assertEqual(str(series.SeriesInstanceUID), source['series_uid'])
            self.assertEqual({str(item.ReferencedSOPInstanceUID) for item in series.ContourImageSequence},
                             set(source['sop_uids']))
            self.assertEqual(len(list((job / 'original').glob('RS_NeuroRT_*.dcm'))), 1)
            self.assertEqual(len(names), 2)
            internal = Path(result['artifacts'][-1]['path'])
            self.assertEqual(internal.read_bytes(), published.read_bytes())

    def test_small_nonempty_roi_marks_incomplete_without_publication(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            job = Path(tmp)
            self.prepare(job, tiny=True)
            self.assertNotEqual(self.run_export(job).returncode, 0)
            manifest = json.loads((job / 'study-manifest.json').read_text())
            self.assertEqual(manifest['export_status'], 'incomplete')
            self.assertFalse(list((job / 'original').glob('RS_NeuroRT_*.dcm')))
            self.assertTrue((job / 'masks/model1.nii.gz').exists())
            self.assertTrue(manifest['export_receipt']['omitted_rois'])

    def test_voxel_focus_sop_plane_and_planarity_remain_strict(self):
        for fault in ('focus', 'plane', 'sop'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
                job = Path(tmp)
                self.prepare(job)
                run = self.run_export(job, writer_fault=fault)
                self.assertNotEqual(run.returncode, 0)
                manifest = json.loads((job / 'study-manifest.json').read_text())
                self.assertEqual(manifest['export_status'], 'incomplete')
                self.assertTrue(manifest['export_receipt']['omitted_rois'])
                self.assertFalse(list((job / 'original').glob('RS_NeuroRT_*.dcm')))

    def test_explicit_ct_reference_uses_same_writer_and_exact_roundtrip(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            job = Path(tmp)
            source = self.prepare(job, modality='CT', model_ids=('synthetic_ct',))
            catalog = {'synthetic_ct': {'id': 'synthetic_ct', 'revision': 'synthetic-1',
                'catalog_state': 'verified', 'classes': [{'class_id': 'tumor', 'label': 'tumor'}]}}
            run = self.run_export(job, catalog=catalog)
            self.assertEqual(run.returncode, 0, run.stderr.decode(errors='replace')[-1800:])
            result = json.loads((job / 'study-manifest.json').read_text())
            self.assertEqual(result['export_status'], 'completed')
            ds = pydicom.dcmread(result['export_receipt']['published_file'])
            self.assertEqual(ds.ApprovalStatus, 'UNAPPROVED')
            self.assertEqual(source['modality'], 'CT')
            self.assertEqual(len(list((job / 'original').glob('RS_NeuroRT_*.dcm'))), 1)

    def test_two_references_export_only_once_each_not_auxiliary(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            for name in ('reference1', 'reference2'):
                job = root / name
                self.prepare(job)
                # The source folder may contain auxiliary acquisitions. The
                # cached writer input contains only the selected reference.
                make_series(job / 'original', z_offset=200)
                run = self.run_export(job)
                self.assertEqual(run.returncode, 0, run.stderr.decode(errors='replace')[-1500:])
                self.assertEqual(len(list((job / 'original').glob('RS_NeuroRT_*.dcm'))), 1)
            outputs = list(root.glob('*/original/RS_NeuroRT_*.dcm'))
            self.assertEqual(len(outputs), 2)
            references = {str(pydicom.dcmread(path).ReferencedFrameOfReferenceSequence[0]
                .RTReferencedStudySequence[0].RTReferencedSeriesSequence[0].SeriesInstanceUID)
                for path in outputs}
            self.assertEqual(len(references), 2)

    def test_nested_classes_remain_three_independent_structures(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            job = Path(tmp)
            self.prepare(job)
            manifest = json.loads((job / 'study-manifest.json').read_text())
            model_id = 'synthetic_nested'
            catalog = {model_id: {'id': model_id, 'revision': 'synthetic-1',
                'catalog_state': 'verified', 'classes': [
                    {'class_id': class_id, 'label': class_id} for class_id in ('WT', 'TC', 'ET')]}}
            masks = []
            for i, class_id in enumerate(('WT', 'TC', 'ET')):
                bits = np.zeros((8, 16, 16), dtype=np.uint8)
                bits[2:5, 2+i:13-i, 2+i:13-i] = 1
                image = sitk.GetImageFromArray(bits)
                image.CopyInformation(sitk.ReadImage(str(job / 'inputs/reference.nii.gz')))
                path = f'masks/{class_id}.nii.gz'
                sitk.WriteImage(image, str(job / path))
                masks.append(MaskArtifact(model_id, class_id, path, geometry(image)).to_dict())
            manifest['requested_model_ids'] = [model_id]
            manifest['results'] = [ModelResult(model_id, 'completed').to_dict()]
            manifest['results'][0]['masks'] = masks
            (job / 'study-manifest.json').write_text(json.dumps(manifest))
            run = self.run_export(job, catalog=catalog)
            self.assertEqual(run.returncode, 0, run.stderr.decode(errors='replace')[-1800:])
            result = json.loads((job / 'study-manifest.json').read_text())
            ds = pydicom.dcmread(result['export_receipt']['published_file'])
            self.assertEqual(len(ds.StructureSetROISequence), 3)
            self.assertEqual(len(result['export_receipt']['delivered_rois']), 3)
            descriptions = ' '.join(str(r.ROIObservationDescription)
                                    for r in ds.RTROIObservationsSequence)
            for class_id in ('WT', 'TC', 'ET'):
                self.assertIn('classe ' + class_id, descriptions)

    def test_publication_failure_keeps_internal_dicom_without_claiming_success(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            job = Path(tmp)
            self.prepare(job)
            run = self.run_export(job, deny_publication=True)
            self.assertNotEqual(run.returncode, 0)
            result = json.loads((job / 'study-manifest.json').read_text())
            self.assertEqual(result['export_status'], 'failed')
            self.assertEqual(result['export_receipt']['published_file'], '')
            self.assertEqual(len(list((job / 'exports').glob('*.dcm'))), 1)
            self.assertFalse(list((job / 'original').glob('RS_NeuroRT_*.dcm')))

    def test_empty_masks_do_not_emit_file_and_changed_original_is_refused(self):
        for empty in (True, False):
            with self.subTest(empty=empty), tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
                job = Path(tmp)
                self.prepare(job, empty=empty)
                if not empty:
                    path = next((job / 'original').glob('*.dcm'))
                    ds = pydicom.dcmread(path)
                    ds.FrameOfReferenceUID = pydicom.uid.generate_uid()
                    ds.save_as(path, enforce_file_format=True)
                run = self.run_export(job)
                result = json.loads((job / 'study-manifest.json').read_text())
                self.assertEqual(result['export_status'], 'empty' if empty else 'failed')
                self.assertEqual(run.returncode, 0 if empty else 1)
                self.assertFalse(list((job / 'original').glob('RS_NeuroRT_*.dcm')))


if __name__ == '__main__':
    unittest.main()

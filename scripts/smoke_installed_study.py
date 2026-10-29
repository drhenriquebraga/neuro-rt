"""Opt-in installed-package study smoke using only freshly generated MR DICOM.

Runs the activated package's unmodified StudyService and model dispatcher with
strict installed resources. A tiny queue/ticket composition isolates this test
from the workstation's real queue and result history. The host's native reader,
writer and viewer modules are invoked by the installed worker subprocesses.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import uuid


def synthetic_series(root):
    import numpy as np
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage, generate_uid
    study, frame = generate_uid(), generate_uid()
    z, y, x = np.indices((16, 32, 32), dtype=float)
    radial = ((x-15.3)/12)**2 + ((y-16.1)/11)**2 + ((z-7.2)/6)**2
    brain = radial < 1
    texture = (np.sin(x*.7) + np.cos(y*.6) + np.sin(z*.9)) * 15
    bump = np.exp(-((x-18)**2+(y-13)**2+((z-8)*1.8)**2)/18)
    values = {
        'FLAIR': (350+420*radial+texture+300*bump)*brain,
        'T1': (900-350*radial+texture-160*bump)*brain,
        'T1c': (880-330*radial+texture+450*bump)*brain,
        'T2': (450+380*radial+texture+250*bump)*brain,
    }
    records = {}
    for number, (role, volume) in enumerate(values.items(), 1):
        folder = root / role
        folder.mkdir(parents=True, exist_ok=False)
        series, sop_uids, files = generate_uid(), [], []
        description = {'T1': 'T1 NATIVE NONCONTRAST', 'T1c': 'T1 CE GAD',
                       'T2': 'T2', 'FLAIR': 'FLAIR'}[role]
        for k in range(16):
            sop = generate_uid()
            meta = FileMetaDataset()
            meta.MediaStorageSOPClassUID, meta.MediaStorageSOPInstanceUID = MRImageStorage, sop
            meta.TransferSyntaxUID, meta.ImplementationClassUID = ExplicitVRLittleEndian, generate_uid()
            path = folder / f'{k:03d}.dcm'
            ds = FileDataset(str(path), {}, file_meta=meta, preamble=b'\0'*128)
            ds.SOPClassUID, ds.SOPInstanceUID = MRImageStorage, sop
            ds.StudyInstanceUID, ds.SeriesInstanceUID, ds.FrameOfReferenceUID = study, series, frame
            ds.PatientName, ds.PatientID = 'SYNTHETIC^INSTALLED_NEURO', 'SYNTHETIC_INSTALLED_R01'
            ds.PatientBirthDate, ds.PatientSex, ds.StudyID = '', '', 'R01'
            ds.StudyDate, ds.StudyTime = '20261029', '120000'
            ds.SeriesDescription, ds.ProtocolName = description, description
            ds.SeriesNumber, ds.InstanceNumber, ds.Modality = number, k+1, 'MR'
            ds.ImagePositionPatient = [20., 30., 40.+k*2.5]
            ds.ImageOrientationPatient = [1., 0., 0., 0., 1., 0.]
            ds.PixelSpacing, ds.SliceThickness = [1.1, 1.4], 2.5
            ds.Rows, ds.Columns = 32, 32
            ds.BitsAllocated, ds.BitsStored, ds.HighBit = 16, 16, 15
            ds.SamplesPerPixel, ds.PhotometricInterpretation, ds.PixelRepresentation = 1, 'MONOCHROME2', 0
            if role == 'T1c': ds.ContrastBolusAgent = 'SYNTHETIC_GAD_METADATA'
            ds.PixelData = np.clip(volume[k], 0, 4095).astype(np.uint16).tobytes()
            ds.save_as(path, enforce_file_format=True)
            sop_uids.append(sop); files.append(str(path))
        ticket = 'synthetic-'+role.lower()
        records[ticket] = {'ticket': ticket, 'series_uid': series, 'subject_key': 'synthetic-r01',
            'study_key': 'synthetic-acquisition-r01', 'modality': 'MR', 'source_format': 'dicom',
            'frame_of_reference_uid': frame, 'sop_instance_uids': sop_uids,
            'metadata': {'SeriesDescription': description, 'ProtocolName': description,
                         'ContrastBolusAgent': 'SYNTHETIC_GAD_METADATA' if role == 'T1c' else ''},
            'source': {'kind': 'dicom', 'input_path': str(folder), 'series_uid': series,
                       'dicom_files': files}}
    return records


class IsolatedQueue:
    def __init__(self): self.events = []; self.finished = []; self.started = time.monotonic()
    def enqueue_study(self, request, study):
        return SimpleNamespace(id=study.study_id)
    def await_turn(self, ticket, event):
        self.events.append({'seconds': time.monotonic()-self.started, 'status': 'lease-acquired'})
        return SimpleNamespace(finish=lambda status: self.finished.append(status))
    def report(self, ticket, value):
        self.events.append({'seconds': time.monotonic()-self.started, **value})
    def cancel(self, ticket): pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-root', type=Path, required=True)
    parser.add_argument('--host-app', type=Path, required=True)
    parser.add_argument('--host-python', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path,
                        help='Isolated data-only override; never changes installed code/resources.')
    parser.add_argument('--overlay-note', default='', help='Describe an authorized code-only fixture overlay.')
    parser.add_argument('--timeout', type=float, default=900)
    args = parser.parse_args()
    host_root = args.host_root.resolve()
    plugin = host_root / 'Plugins/NEURO RT'
    state = json.loads((plugin/'installation.json').read_text(encoding='utf-8'))
    if state['state'] != 'ready': raise ValueError('A instalação precisa estar ativada.')
    code = plugin/'versions'/state['active_version']
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(code))
    from neuro_rt.plugin_paths import resolve_plugin_paths
    from neuro_rt.service import Settings
    from neuro_rt.study_service import StudyService, TERMINAL
    from neuro_rt.model_registry import load_catalog
    import neuro_rt.study_service as imported_service
    if not Path(imported_service.__file__).resolve().is_relative_to(code):
        raise ValueError('O teste precisa usar exclusivamente o código instalado.')
    paths = resolve_plugin_paths(host_root, state)
    settings = Settings(code, plugin_paths=paths)
    if args.data_dir is not None:
        settings.data_dir = args.data_dir.resolve()
    # Host sources and its embedded Python are read-only dependencies of this
    # same-machine fixture. No installation/global host configuration is edited.
    settings.host_app, settings.host_python = args.host_app.resolve(), str(args.host_python.resolve())
    if not Path(settings.host_python).is_file(): raise FileNotFoundError(settings.host_python)
    ident = 'installed-real-'+uuid.uuid4().hex[:12]
    fixture = settings.data_dir/'r01-synthetic-studies'/ident
    fixture.mkdir(parents=True, exist_ok=False)
    print('SYNTHETIC_FIXTURE '+str(fixture), flush=True)
    os.environ.update(TEMP=str(fixture), TMP=str(fixture), MPLCONFIGDIR=str(fixture),
                      PYTHONDONTWRITEBYTECODE='1')
    records = synthetic_series(fixture/'DICOM')
    queue, registrations = IsolatedQueue(), []
    host = SimpleNamespace(queue_bridge=queue, device_preference=lambda: 'cpu',
        resolve_series_ticket=lambda t: records[t], register_result=registrations.append)
    model_id = 'glioma_attention_unet3d'
    catalog = {s['id']: s for s in load_catalog(code/'catalog/models.json') if s['id'] == model_id}
    service = StudyService(settings, host, catalog=catalog)
    payload = {'schema': 'neuro-rt/request/2', 'request_id': ident, 'explicit_request': True,
        'export_rtstruct': True, 'device': 'cpu', 'studies': [{'study_id': ident,
        'reference': 'synthetic-t1c', 'model_ids': [model_id], 'bindings_by_model': {model_id: [
            {'role': role, 'series_ticket': 'synthetic-'+role.lower(), 'certainty': 'certain',
             'association_source': 'manual'} for role in ('FLAIR', 'T1', 'T1c', 'T2')]}}]}
    start = time.monotonic()
    try:
        service.submit(payload)
        last = None
        while True:
            job = service.job(ident)
            if job['status'] != last:
                print(json.dumps({'elapsed': round(time.monotonic()-start, 2), 'status': job['status']}), flush=True)
                last = job['status']
            if job['status'] in TERMINAL: break
            if time.monotonic()-start > args.timeout:
                service.cancel(ident)
                raise TimeoutError('O smoke ultrapassou o prazo; cancelamento solicitado.')
            time.sleep(.25)
        directory = settings.data_dir/'jobs'/ident
        manifest_path = directory/'study-manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.is_file() else None
        report = {'synthetic_only': True, 'same_physical_station': True,
            'installed_code': str(code), 'service_module': imported_service.__file__,
            'host_app': str(settings.host_app), 'host_python': settings.host_python,
            'model_python': settings.runtime_python(catalog[model_id]['runtime_id']),
            'strict_installed_resources': settings.plugin_paths is not None,
            'installed_data_root': str(paths.data_dir), 'effective_data_root': str(settings.data_dir),
            'model_spec': catalog[model_id], 'model_root': str(settings.models_dir),
            'fixture': str(fixture), 'job_dir': str(directory), 'seconds': time.monotonic()-start,
            'job': job, 'manifest': manifest, 'queue_events': queue.events,
            'queue_finished': queue.finished, 'registered_results': len(registrations)}
        inventory = json.loads((code/'release-manifest.json').read_text(encoding='utf-8'))
        originals = {e['path'][5:]: e['sha256'] for e in inventory['files']
                     if e['path'].startswith('code/') and e['path'].endswith('.py')}
        report['code_overlay_note'] = args.overlay_note
        report['code_changes_from_original_payload'] = []
        for file in (code/'neuro_rt').rglob('*.py'):
            relative = file.relative_to(code).as_posix()
            with file.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            expected = originals.get(relative)
            if actual != expected:
                report['code_changes_from_original_payload'].append({
                    'path': relative, 'original_payload_sha256': expected, 'observed_sha256': actual})
        if manifest:
            import nibabel as nib
            import numpy as np
            reference = nib.load(str(directory/'inputs/reference.nii.gz'))
            report['mask_geometry_checks'] = []
            for result in manifest['results']:
                for mask in result['masks']:
                    image = nib.load(mask['path'])
                    check = {'class_id': mask['class_id'], 'shape': list(image.shape),
                        'geometry_equal': image.shape == reference.shape and
                            bool(np.allclose(image.affine, reference.affine, atol=1e-4)),
                        'voxels': int(np.count_nonzero(np.asanyarray(image.dataobj)))}
                    report['mask_geometry_checks'].append(check)
                    if not check['geometry_equal']: raise ValueError('Máscara fora da grade de referência.')
        (fixture/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('REPORT '+str(fixture/'report.json'), flush=True)
        if job['status'] not in ('completed','empty'):
            raise RuntimeError('O estudo instalado não concluiu; consulte os registros no relatório.')
    finally:
        service.close()


if __name__ == '__main__': main()

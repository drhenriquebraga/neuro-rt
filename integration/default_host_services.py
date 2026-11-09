"""Bind the plugin to the Local Suite owners, without a second reader or queue."""
import hashlib
import hmac
import os
from pathlib import Path


def bindings_for_host(host_info, cfg=None):
    cfg = dict(cfg or {})
    secret = os.urandom(32)
    def identity(value):
        return hmac.new(secret, str(value).encode('utf-8'), hashlib.sha256).hexdigest()

    def resolve_series_ticket(ticket):
        import radai_thumbnail
        import pydicom
        folder, uid = radai_thumbnail.resolver(ticket)
        series = radai_thumbnail.serie_do_bilhete(ticket) if folder else None
        if not series or str(series.get('uid')) != str(uid):
            raise ValueError('Seleção de série expirada. Carregue novamente a pasta.')
        files = [str(f['caminho']) for f in series.get('arquivos', [])]
        if not files: raise ValueError('A série não possui cortes legíveis.')
        ds = pydicom.dcmread(files[0], stop_before_pixels=True)
        modality = str(ds.get('Modality', ''))
        if modality not in ('MR', 'CT'): raise ValueError('Selecione uma série de RM ou TC.')
        study = str(ds.get('StudyInstanceUID', ''))
        if not study: raise ValueError('A série não informa o estudo DICOM.')
        subject = str(ds.get('PatientID', '')) + '\0' + str(ds.get('IssuerOfPatientID', ''))
        if not subject.strip('\0'): subject = 'study:' + study
        metadata = {name: str(ds.get(name, '')) for name in ('SeriesDescription', 'ProtocolName',
            'ContrastBolusAgent', 'RepetitionTime', 'EchoTime')}
        return {'ticket': ticket, 'series_uid': str(uid), 'subject_key': identity(subject),
            'study_key': identity(study), 'modality': modality, 'source_format': 'dicom',
            'geometry': {}, 'metadata': metadata,
            'frame_of_reference_uid': str(ds.get('FrameOfReferenceUID', '')),
            'sop_instance_uids': [str(f.get('sop') or '') for f in series['arquivos']],
            'source': {'kind': 'dicom', 'input_path': str(folder), 'dicom_files': files,
                       'series_uid': str(uid)}}

    def preference():
        import radai_config
        path = cfg.get('caminho')
        values = radai_config.ler_arquivo(path)[1] if path else {}
        raw = str(values.get('DEVICE', values.get('device', 'auto'))).strip().lower()
        return {'gpu': 'cuda', 'cuda': 'cuda', 'cpu': 'cpu'}.get(raw, 'auto')

    def register_result(receipt):
        manifest = receipt['manifest']
        exported = manifest.get('export_receipt')
        if manifest.get('export_status') != 'completed' or not exported: return
        published = exported.get('published_file')
        if not isinstance(published, str) or not published: return
        try:
            path = Path(published)
            if not path.is_absolute() or not path.is_file(): return
        except (OSError, ValueError):
            return
        import radai_archive
        ok = radai_archive.registrar_serie(manifest['reference']['series_uid'], str(path.parent),
            path.name, estruturas=len(exported['delivered_rois']),
            ver='NeuroRT ' + manifest['plugin_version'])
        if not ok: raise RuntimeError('O acervo não confirmou o registro do resultado.')

    def export_rtstruct(*args, **kwargs):
        # Only workers call this capability; the UI process never loads engine.
        from neuro_rt.export_study import export_study
        return export_study(*args, **kwargs)

    return {'resolve_series_ticket': resolve_series_ticket, 'device_preference': preference,
        'register_result': register_result, 'export_rtstruct': export_rtstruct,
        'viewer_routes': {'series': '/neuro/api/studies/{study_id}',
                          'artifact': '/neuro/api/studies/{study_id}/artifacts/{artifact_id}'}}

"""Bind the plugin to the Local Suite owners, without a second reader or queue."""
import hashlib
import hmac
import os
from pathlib import Path
import math


def _picker_geometry(header, files):
    """Physical grid from the host's already indexed, sorted DICOM slices."""
    if len(files) < 2:
        return {}
    try:
        axes = [float(x) for x in header.ImageOrientationPatient]
        row, col = axes[:3], axes[3:]
        dy, dx = map(float, header.PixelSpacing)
        first = [float(x) for x in files[0]['ipp']]
        last = [float(x) for x in files[-1]['ipp']]
        step = [(b-a)/(len(files)-1) for a,b in zip(first,last,strict=True)]
        dz = math.hypot(*step)
        if min(dx, dy, dz) <= 0 or len(step) != 3 or len(axes) != 6:
            return {}
        direction = [v for axis in zip(row, col, [x/dz for x in step]) for v in axis]
        if not all(map(math.isfinite, [*direction,*first,dx,dy,dz])):
            return {}
        return {'size_xyz':[int(header.Columns), int(header.Rows), len(files)],
                'spacing_xyz_mm':[dx,dy,dz], 'origin_lps_mm':first, 'direction_lps':direction}
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, ZeroDivisionError):
        return {}


def _preview_header(ds):
    """Technical display values for the local viewer, including enhanced MR/CT."""
    fields = []
    groups = getattr(ds, 'SharedFunctionalGroupsSequence', [])[:1] + getattr(ds, 'PerFrameFunctionalGroupsSequence', [])[:1]
    def tag(name, sequence=None, alternate=None):
        value = ds.get(name)
        if value is None and sequence:
            for group in groups:
                items = group.get(sequence)
                if items:
                    value = items[0].get(alternate or name)
                    if value is not None:
                        break
        return value
    def add(label, value, unit=''):
        if value is not None and str(value).strip():
            fields.append([label, str(value).strip()[:128] + unit])
    add('Série', tag('SeriesNumber'))
    add('Descrição', tag('SeriesDescription'))
    add('Protocolo', tag('ProtocolName'))
    if ds.get('Rows') and ds.get('Columns'):
        add('Matriz', f'{ds.Rows} × {ds.Columns}')
    def number(value):
        try:
            return format(float(value), '.8g')
        except (ValueError, TypeError, OverflowError):
            return None
    spacing = tag('PixelSpacing', 'PixelMeasuresSequence')
    if spacing is not None and not isinstance(spacing, str):
        try:
            values = [number(n) for n in spacing]
            if len(values) == 2 and all(values):
                add('Espaçamento no plano', ' × '.join(values), ' mm')
        except TypeError:
            pass
    add('Espessura', number(tag('SliceThickness', 'PixelMeasuresSequence')), ' mm')
    add('Intervalo entre cortes', number(tag('SpacingBetweenSlices', 'PixelMeasuresSequence')), ' mm')
    if ds.get('Modality') == 'MR':
        add('Aquisição RM', tag('MRAcquisitionType'))
        add('B₀', number(tag('MagneticFieldStrength')), ' T')
        add('TR', number(tag('RepetitionTime', 'MRTimingAndRelatedParametersSequence')), ' ms')
        add('TE', number(tag('EchoTime', 'MREchoSequence', 'EffectiveEchoTime')), ' ms')
        add('TI', number(tag('InversionTime')), ' ms')
        add('Flip angle', number(tag('FlipAngle', 'MRTimingAndRelatedParametersSequence')), '°')
        add('Contraste', tag('ContrastBolusAgent'))
    if ds.get('Modality') == 'CT':
        add('kVp', number(tag('KVP')))
        add('Kernel', tag('ConvolutionKernel'))
    return fields


def bindings_for_host(host_info, cfg=None):
    cfg = dict(cfg or {})
    secret = os.urandom(32)
    def identity(value):
        return hmac.new(secret, str(value).encode('utf-8'), hashlib.sha256).hexdigest()

    def resolve_series_ticket(ticket, *, picker=False):
        import radai_thumbnail
        import pydicom
        folder, uid = radai_thumbnail.resolver(ticket)
        series = radai_thumbnail.serie_do_bilhete(ticket) if folder else None
        if not series or str(series.get('uid')) != str(uid):
            raise ValueError('Seleção de série expirada. Carregue novamente a pasta.')
        files = [str(f['caminho']) for f in series.get('arquivos', [])]
        if not files: raise ValueError('A série não possui cortes legíveis.')
        try:
            ds = pydicom.dcmread(files[0], stop_before_pixels=True, force=True)
        except (pydicom.errors.InvalidDicomError, OSError, ValueError, EOFError) as exc:
            raise ValueError('A série não possui cortes legíveis.') from exc
        modality = str(ds.get('Modality', ''))
        if str(ds.get('SeriesInstanceUID', '')) != str(uid):
            raise ValueError('Seleção de série expirada. Carregue novamente a pasta.')
        if modality not in ('MR', 'CT'): raise ValueError('Selecione uma série de RM ou TC.')
        study = str(ds.get('StudyInstanceUID', ''))
        if not study: raise ValueError('A série não informa o estudo DICOM.')
        subject = str(ds.get('PatientID', '')) + '\0' + str(ds.get('IssuerOfPatientID', ''))
        if not subject.strip('\0'): subject = 'study:' + study
        metadata = {name: str(ds.get(name, '')) for name in ('SeriesDescription', 'SeriesNumber', 'ProtocolName',
            'ContrastBolusAgent', 'RepetitionTime', 'EchoTime')}
        display = ({'picker_identity': {key:str(ds.get(tag, '')).strip()[:128] for key, tag in (
            ('patient_name','PatientName'),('patient_id','PatientID'),('study_date','StudyDate'))}}
            if picker else {})
        return {'ticket': ticket, 'series_uid': str(uid), 'subject_key': identity(subject), **display,
            'study_key': identity(study), 'modality': modality, 'source_format': 'dicom',
            'geometry': _picker_geometry(ds, series['arquivos']), 'metadata': metadata,
            'preview_header': _preview_header(ds),
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

    from contextlib import contextmanager
    @contextmanager
    def protocol_storage():
        import radai_config
        config_path = cfg.get('caminho') or radai_config.caminho_padrao()
        with radai_config._editar_personalizadas(config_path):
            yield Path(config_path).with_name('protocolos_neuro.json')

    return {'resolve_series_ticket': resolve_series_ticket, 'device_preference': preference,
        'resolve_picker_ticket': lambda ticket: resolve_series_ticket(ticket, picker=True),
        'protocol_storage': protocol_storage,
        'register_result': register_result, 'export_rtstruct': export_rtstruct,
        'viewer_routes': {'series': '/neuro/api/studies/{study_id}',
                          'artifact': '/neuro/api/studies/{study_id}/artifacts/{artifact_id}'}}

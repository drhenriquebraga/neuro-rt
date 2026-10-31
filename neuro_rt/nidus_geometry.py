"""Editable manual geometric suggestions; the host remains the RTSTRUCT writer."""
import json
import hashlib
import math
import os
from pathlib import Path
import shutil
import uuid
import copy
import re


class NidusCandidate:
    def __init__(self, core, temperature, *, progress=None):
        self.core = core
        self.temperature = core.temperature(temperature)
        self.geometry = dict(core.geometry)
        self.eixos = core.eixos
        self.packed = core.packed(self.temperature, progress=progress)
        self.view_shape = tuple(self.packed.shape[index] for index in self.eixos[0])
        self.history, self.edited, self.revision = [], False, 1
        self.untracked_edits = False
        self.id = uuid.uuid4().hex

    def _indices(self, axis, index):
        if type(axis) is not int or axis not in (0, 1, 2) or type(index) is not int or not 0 <= index < self.view_shape[axis]:
            raise ValueError('Plano de edição fora da referência.')
        native_axis = self.eixos[0][axis]
        native_index = self.view_shape[axis]-1-index if self.eixos[1][axis] else index
        return native_axis, native_index

    def plane(self, axis, index):
        import numpy as np
        import radai_projection as N
        native_axis, native_index = self._indices(axis, index)
        thin = np.expand_dims(self.packed.fatia(native_axis, native_index), axis=native_axis)
        return N.corte(N.para_lps(thin, self.eixos), axis, 0).copy()

    def _set_plane(self, axis, index, plane):
        import numpy as np
        native_axis, native_index = self._indices(axis, index)
        view = np.expand_dims(plane if axis == 0 else plane[::-1], axis=axis)
        for dimension, inverted in enumerate(self.eixos[1]):
            if inverted:
                view = np.flip(view, axis=dimension)
        native = np.transpose(view, np.argsort(self.eixos[0]))
        native = np.squeeze(native, axis=native_axis)
        if native_axis == 0:
            self.packed.bits[native_index] = np.packbits(native, axis=-1)
        elif native_axis == 1:
            self.packed.bits[:, native_index] = np.packbits(native, axis=-1)
        else:
            byte, bit = divmod(native_index, 8)
            flag = 1 << (7-bit)
            target = self.packed.bits[:, :, byte]
            target[:] = (target & (255-flag)) | (native.astype(np.uint8)*flag)

    def edit(self, axis, index, polygon, operation):
        import numpy as np
        import radai_projection as N
        if operation not in ('add', 'remove') or not isinstance(polygon, list) or not 3 <= len(polygon) <= 120:
            raise ValueError('Edição manual inválida.')
        try:
            points = [(float(p[0]), float(p[1])) for p in polygon]
        except (TypeError, ValueError, IndexError):
            raise ValueError('Traço manual inválido.') from None
        if not all(math.isfinite(v) and 0 <= v <= 1 for p in points for v in p):
            raise ValueError('Traço manual fora do plano de referência.')
        before = self.plane(axis, index)
        height, width = before.shape
        delta = N._mascara_poligono([(x*width, y*height) for x, y in points], height, width)
        result = before | delta if operation == 'add' else before & ~delta
        self.history.append((axis, index, np.packbits(before.reshape(-1)), before.shape))
        while len(self.history) > 60 or sum(item[2].nbytes for item in self.history) > 16*1024*1024:
            self.history.pop(0)
            self.untracked_edits = True
        self._set_plane(axis, index, result)
        self.edited = True
        self.revision += 1

    def undo(self):
        import numpy as np
        if not self.history:
            return False
        axis, index, bits, shape = self.history.pop()
        self._set_plane(axis, index, np.unpackbits(bits, count=math.prod(shape)).reshape(shape).astype(bool))
        self.edited = bool(self.history) or self.untracked_edits
        self.revision += 1
        return True

    def mask(self):
        import numpy as np
        return np.unpackbits(self.packed.bits, axis=-1, count=self.packed.shape[2]).astype(bool)

    def fork(self):
        """Edit a packed snapshot, publishing it only after persistence succeeds."""
        import radai_projection as N
        result = copy.copy(self)
        result.packed = N.Compacto(self.packed.bits.copy(), self.packed.shape)
        result.history = list(self.history)
        return result

    def metadata(self):
        return {'candidate': self.id, 'temperature': self.temperature, 'revision': self.revision,
                'edited': self.edited, 'approval_status': 'UNAPPROVED',
                'empty': not bool(self.packed.bits.any()),
                'incidence_count': len(getattr(self.core, 'fields', [])),
                'incidence_digest': getattr(self.core, 'incidence_digest', ''),
                'algorithm': 'manual-projection-distance-quantile/1', 'geometry': self.geometry}

    def save(self, folder, *, checkpoint=lambda: None):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / 'candidate.json'
        previous = None
        if target.is_file():
            try:
                previous = json.loads(target.read_text(encoding='utf-8')).get('mask')
            except (ValueError, OSError):
                pass
        raw = folder / ('mask-' + str(self.revision) + '.bits')
        temporary = raw.with_suffix('.part')
        with temporary.open('wb') as stream:
            stream.write(self.packed.bits.tobytes())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, raw)
        metadata = self.metadata()
        metadata.update(mask=raw.name, native_shape=list(self.packed.shape))
        metadata['incidences'] = getattr(self.core, 'incidences', [])
        temporary_metadata = folder / 'candidate.json.part'
        with temporary_metadata.open('w', encoding='utf-8') as stream:
            json.dump(metadata, stream, ensure_ascii=True)
            stream.flush()
            os.fsync(stream.fileno())
        checkpoint()
        os.replace(temporary_metadata, target)
        # Publish the pointer first. Never remove its mask or the last committed
        # revision; orphan files from interrupted writes are collected next time.
        keep = {raw.name, previous}
        for entry in folder.iterdir():
            if (re.fullmatch(r'mask-[0-9]+\.bits', entry.name) and entry.name not in keep
                    and not entry.is_symlink() and entry.is_file()):
                try:
                    entry.unlink()
                except OSError:
                    pass  # cleanup cannot invalidate a successfully committed revision


def contour_segments(plane):
    """Include the reference border, including the star-shaped T=0 union."""
    import numpy as np
    import radai_projection as N
    padded = np.pad(plane, 1)[None, ...]
    return [((x0-1, y0-1), (x1-1, y1-1))
            for (x0, y0), (x1, y1) in N.contorno_do_tubo(padded, 0, 0)]


def source_signature(folder, series_uid):
    """Private identity fingerprint, captured when the source is first opened."""
    import pydicom
    import SimpleITK as sitk
    tags = ['SOPInstanceUID', 'SeriesInstanceUID', 'FrameOfReferenceUID',
            'StudyInstanceUID', 'PatientID', 'IssuerOfPatientID']
    files = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(str(folder), str(series_uid))
    if not files:
        raise ValueError('A referência DICOM está indisponível.')
    headers = [pydicom.dcmread(file, stop_before_pixels=True, specific_tags=tags) for file in files]
    if any(not all(tag in header for tag in tags[:4]) or str(header.SeriesInstanceUID) != str(series_uid)
           for header in headers):
        raise ValueError('Referências DICOM incompletas.')
    values = sorted(tuple(str(header.get(tag, '')) for tag in tags) for header in headers)
    return hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()


def export_candidate(candidate, source_folder, series_uid, host_root, work, *, checkpoint=lambda: None,
                     expected_signature=None):
    """Export a single original DICOM reference through the existing host writer.

    Paths are supplied by the trusted ticket resolver, never by HTTP JSON. The
    generated DICOM remains private until its metadata and exact voxel round trip
    pass. No original series file is overwritten or used as an output directory.
    """
    import numpy as np
    from .imaging import geometry, load_input
    from .export_study import _check_written
    from integration.host_imports import prepare_host_imports
    checkpoint()
    initial_signature = source_signature(source_folder, series_uid)
    if expected_signature is not None and initial_signature != expected_signature:
        raise ValueError('As referências DICOM mudaram desde a gravação das incidências.')
    image, source = load_input(source_folder, series_uid, allowed_modalities=('MR', 'CT'))
    expected_geometry = {key: candidate.geometry[value] for key, value in (
        ('size_xyz', 'size'), ('spacing_xyz_mm', 'spacing'),
        ('origin_lps_mm', 'origin'), ('direction_lps', 'direction'))}
    if set(geometry(image)) != set(expected_geometry) or any(
            not np.allclose(geometry(image)[key], expected_geometry[key], rtol=0, atol=1e-5)
            for key in expected_geometry):
        raise ValueError('A referência original mudou; refaça o consenso antes de exportar.')
    mask = candidate.mask()
    if mask.shape != tuple(reversed(image.GetSize())) or not mask.any():
        raise ValueError('O consenso está vazio ou não corresponde à referência original.')
    work = Path(work)
    original = work / ('reference-' + uuid.uuid4().hex)
    original.mkdir(parents=True)
    for number, file in enumerate(source['dicom_files']):
        shutil.copyfile(file, original / ('%06d.dcm' % number))
    checkpoint()
    prepare_host_imports(host_root)
    import engine
    key, name = 'NidusGeo', 'NidusGeo_ai'
    description = ('Sugestao geometrica manual nao aprovada. NeuroRT / modelo geometrico_Nidus / classe consenso. '
                   'Sem inferencia, pesos ou probabilidade clinica; sem CTV ou fusao RM-TC. '
                   'Temperatura %.3f; revisao %d; editado %s; algoritmo manual-projection-distance-quantile/1.'
                   % (candidate.temperature, candidate.revision, candidate.edited))
    description += ' Incidencias %d; SHA256 %s.' % (len(getattr(candidate.core, 'incidences', [])),
                                                   getattr(candidate.core, 'incidence_digest', ''))
    path, _ = engine.build_rtstruct(str(original), {key: mask}, cru=True, descontar=False,
        suavizar_mm=0., decimar_mm=0., modalidade=source['modality'], rotulo='NIDUS_GEOM',
        origem={key: 'neuro-rt/nidus-geometric'}, observacoes={key: description})
    checkpoint()
    ds, delivered, omitted = _check_written(path, source, {name: mask}, original)
    if omitted or delivered != [name]:
        raise ValueError('O gravador não conservou o contorno completo; máscara mantida para revisão.')
    current_image, current_source = load_input(source_folder, series_uid, allowed_modalities=('MR', 'CT'))
    if (current_source['sop_uids'] != source['sop_uids'] or current_source['frame_uid'] != source['frame_uid']
            or any(not np.allclose(geometry(current_image)[key], expected_geometry[key], atol=1e-5, rtol=0)
                   for key in expected_geometry)):
        raise ValueError('As imagens de referência mudaram durante a exportação.')
    checkpoint()
    if source_signature(source_folder, series_uid) != initial_signature:
        raise ValueError('As referências DICOM mudaram durante a exportação.')
    destination = work / ('RS_Nidus_Sugestao_' + uuid.uuid4().hex + '.dcm')
    temporary = destination.with_suffix('.part')
    shutil.copyfile(path, temporary)
    os.replace(temporary, destination)
    return destination

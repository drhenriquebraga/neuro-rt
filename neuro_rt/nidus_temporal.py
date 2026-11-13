"""Read real, geometry-checked MR time points without changing the NIDUS reference.

Only temporal DICOM indices, or explicit dynamic acquisitions with coherent real
timestamps, establish time. TOF slabs, filenames and InstanceNumber never do.
Private descriptors contain paths/UIDs; public() deliberately exposes neither.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timezone
from pathlib import Path
import math
import re
import secrets

import numpy as np
import pydicom

MAX_PHASES = 64
MAX_FILES = 24000
MAX_PLANES = 48000
MAX_VOLUME_BYTES = 512 * 1024 * 1024
_DYNAMIC = re.compile(r'\b(TRICKS|TWIST|TR-MRA|DYNAMIC|DYNAMIQUE|DINAMIC[AO]|TIME.?RESOLVED)\b', re.I)
_PROJECTION = re.compile(r'\b(MIP|MINIP|MPR|VOLUME.?RENDER|VR)\b', re.I)
_TAGS = ['SOPClassUID', 'SOPInstanceUID', 'PatientID', 'IssuerOfPatientID',
         'StudyInstanceUID', 'SeriesInstanceUID', 'FrameOfReferenceUID', 'Modality',
         'Rows', 'Columns', 'ImageOrientationPatient', 'ImagePositionPatient',
         'PixelSpacing', 'SliceThickness', 'SamplesPerPixel', 'PhotometricInterpretation',
         'NumberOfFrames', 'ImageType', 'SeriesDescription', 'ProtocolName', 'SequenceName',
         'MRAcquisitionType', 'TemporalPositionIdentifier', 'NumberOfTemporalPositions',
         'TemporalResolution', 'AcquisitionNumber', 'AcquisitionDateTime', 'AcquisitionDate',
         'AcquisitionTime', 'RescaleSlope', 'RescaleIntercept',
         'SharedFunctionalGroupsSequence', 'PerFrameFunctionalGroupsSequence']


class TemporalError(ValueError):
    """The code is public; never include a DICOM value or path in the message."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _float_tuple(value, count):
    try:
        result = tuple(float(v) for v in value)
        if len(result) != count or not all(math.isfinite(v) for v in result):
            raise ValueError()
        return result
    except (TypeError, ValueError, OverflowError):
        raise TemporalError('INVALID_GEOMETRY') from None


def _integer(value, default=None):
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError, OverflowError):
        return default


def _first(ds, name):
    seq = getattr(ds, name, None)
    return seq[0] if seq and len(seq) == 1 else None


def _fg_value(per, shared, sequence, attribute, default=None):
    for ds in (per, shared):
        item = _first(ds, sequence) if ds is not None else None
        if item is not None and hasattr(item, attribute):
            return getattr(item, attribute)
    return default


def _timestamp(ds, per=None):
    value = _fg_value(per, None, 'FrameContentSequence', 'FrameReferenceDateTime')
    value = value or _fg_value(per, None, 'FrameContentSequence', 'FrameAcquisitionDateTime')
    value = value or getattr(ds, 'AcquisitionDateTime', None)
    if not value:
        date, clock = str(getattr(ds, 'AcquisitionDate', '')), str(getattr(ds, 'AcquisitionTime', ''))
        if len(date) != 8 or len(clock.split('.')[0]) < 6:
            return None
        value = date + clock
    try:
        # A complete date+seconds is required. A SeriesTime is not acquisition time.
        if len(str(value).split('.')[0].split('+')[0].split('-')[0]) < 14:
            return None
        dt = pydicom.valuerep.DT(value)
        return dt.replace(tzinfo=dt.tzinfo or timezone.utc).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


@dataclass(frozen=True)
class Plane:
    path: str = field(repr=False)
    file_stamp: tuple = field(repr=False)
    frame_index: int | None
    sop: str = field(repr=False)
    uid: str = field(repr=False)
    identity: tuple = field(repr=False)
    protocol: tuple = field(repr=False)
    rows: int
    columns: int
    orientation: tuple
    position: tuple
    spacing: tuple
    temporal: int | None
    acquisition: int | None
    timestamp: float | None
    temporal_resolution: float | None
    dynamic: bool
    projection: bool
    declared_count: int | None
    slope: float
    intercept: float
    mono1: bool
    stack: str = field(repr=False, default='')


@dataclass(frozen=True)
class Frame:
    planes: tuple = field(repr=False)
    ordinal: int
    time_seconds: float | None


@dataclass(frozen=True)
class Group:
    frames: tuple = field(repr=False)
    kind: str
    evidence: str
    id: str = field(default_factory=lambda: secrets.token_urlsafe(24))

    def public(self):
        return {'id': self.id, 'kind': self.kind, 'count': len(self.frames),
                'can_rotate': self.kind == 'volume3d', 'evidence': self.evidence,
                'timing_known': all(f.time_seconds is not None for f in self.frames),
                'frames': [{'index': i, 'time_seconds': f.time_seconds}
                           for i, f in enumerate(self.frames)]}


@dataclass
class Discovery:
    groups: list
    rejected: list


@dataclass
class FrameData:
    array: np.ndarray
    spacing: tuple
    origin: tuple
    direction: tuple
    mono1: bool = False

    def image(self):
        import SimpleITK as sitk
        image = sitk.GetImageFromArray(self.array)
        image.SetSpacing(self.spacing)
        image.SetOrigin(self.origin)
        image.SetDirection(self.direction)
        return image


def _planes(path, ds):
    if str(getattr(ds, 'Modality', '')) != 'MR':
        return []
    identity = tuple(str(getattr(ds, tag, '')) for tag in
                     ('PatientID', 'IssuerOfPatientID', 'StudyInstanceUID', 'FrameOfReferenceUID'))
    if any(not identity[i] for i in (0, 2, 3)):
        raise TemporalError('MISSING_IDENTITY')
    uid, sop = str(getattr(ds, 'SeriesInstanceUID', '')), str(getattr(ds, 'SOPInstanceUID', ''))
    if not uid or not sop:
        raise TemporalError('MISSING_IDENTITY')
    rows, cols = _integer(getattr(ds, 'Rows', None), 0), _integer(getattr(ds, 'Columns', None), 0)
    if min(rows, cols) < 2 or rows * cols * 4 > MAX_VOLUME_BYTES:
        raise TemporalError('INVALID_GEOMETRY')
    photo = str(getattr(ds, 'PhotometricInterpretation', ''))
    if _integer(getattr(ds, 'SamplesPerPixel', 1)) != 1 or photo not in ('MONOCHROME1', 'MONOCHROME2'):
        raise TemporalError('UNSUPPORTED_PIXEL_FORMAT')
    protocol = tuple(str(getattr(ds, tag, '')).strip().upper() for tag in
                     ('ProtocolName', 'SequenceName', 'MRAcquisitionType'))
    description = str(getattr(ds, 'SeriesDescription', ''))
    image_type = '\\'.join(str(x) for x in getattr(ds, 'ImageType', []))
    dynamic = bool(_DYNAMIC.search(' '.join(protocol) + ' ' + description))
    projection = bool(_PROJECTION.search(image_type + ' ' + description))
    count = _integer(getattr(ds, 'NumberOfFrames', 1), 0)
    if not 1 <= count <= MAX_PLANES:
        raise TemporalError('RESOURCE_LIMIT')
    shared = _first(ds, 'SharedFunctionalGroupsSequence')
    per_frames = getattr(ds, 'PerFrameFunctionalGroupsSequence', None)
    if count > 1 and (not per_frames or len(per_frames) != count):
        raise TemporalError('MULTIFRAME_WITHOUT_TEMPORAL_GEOMETRY')
    stamp = path.stat()
    result = []
    for index in range(count):
        per = per_frames[index] if per_frames else None
        orientation = _float_tuple(_fg_value(per, shared, 'PlaneOrientationSequence',
                                  'ImageOrientationPatient', getattr(ds, 'ImageOrientationPatient', None)), 6)
        position = _float_tuple(_fg_value(per, shared, 'PlanePositionSequence',
                               'ImagePositionPatient', getattr(ds, 'ImagePositionPatient', None)), 3)
        spacing = _float_tuple(_fg_value(per, shared, 'PixelMeasuresSequence',
                              'PixelSpacing', getattr(ds, 'PixelSpacing', None)), 2)
        if min(spacing) <= 0:
            raise TemporalError('INVALID_GEOMETRY')
        temporal = _integer(_fg_value(per, None, 'FrameContentSequence', 'TemporalPositionIndex'))
        if count == 1:
            temporal = temporal or _integer(getattr(ds, 'TemporalPositionIdentifier', None))
        elif temporal is None:
            # Per-frame indices are essential: a 4-D multiframe is never a z stack.
            raise TemporalError('MULTIFRAME_WITHOUT_TEMPORAL_GEOMETRY')
        slope = float(_fg_value(per, shared, 'PixelValueTransformationSequence', 'RescaleSlope', getattr(ds, 'RescaleSlope', 1)))
        intercept = float(_fg_value(per, shared, 'PixelValueTransformationSequence', 'RescaleIntercept', getattr(ds, 'RescaleIntercept', 0)))
        if not math.isfinite(slope) or not math.isfinite(intercept) or slope <= 0:
            raise TemporalError('INVALID_PIXEL_TRANSFORM')
        resolution = getattr(ds, 'TemporalResolution', None)
        resolution = float(resolution) / 1000 if resolution is not None else None
        result.append(Plane(str(path), (stamp.st_size, stamp.st_mtime_ns), index if count > 1 else None,
                            sop, uid, identity, protocol, rows, cols, orientation, position, spacing,
                            temporal, _integer(getattr(ds, 'AcquisitionNumber', None)),
                            _timestamp(ds, per), resolution, dynamic, projection,
                            _integer(getattr(ds, 'NumberOfTemporalPositions', None)), slope, intercept,
                            photo == 'MONOCHROME1', str(_fg_value(per, None, 'FrameContentSequence', 'StackID', ''))))
    return result


def _check_grid(planes):
    first = planes[0]
    orientation = np.array(first.orientation)
    row, col = orientation[:3], orientation[3:]
    normal = np.cross(row, col)
    if (not np.isclose(np.linalg.norm(row), 1, atol=1e-5) or
            not np.isclose(np.linalg.norm(col), 1, atol=1e-5) or
            not np.isclose(row @ col, 0, atol=1e-5)):
        raise TemporalError('INVALID_GEOMETRY')
    for plane in planes:
        if (plane.identity != first.identity or (plane.rows, plane.columns) != (first.rows, first.columns) or
                not np.allclose(plane.orientation, first.orientation, atol=1e-5, rtol=0) or
                not np.allclose(plane.spacing, first.spacing, atol=1e-5, rtol=0) or plane.mono1 != first.mono1):
            raise TemporalError('MIXED_GEOMETRY_OR_IDENTITY')
    ordered = tuple(sorted(planes, key=lambda p: np.dot(p.position, normal)))
    if len({(p.sop, p.frame_index) for p in ordered}) != len(ordered):
        raise TemporalError('DUPLICATE_SOURCE')
    positions = np.asarray([p.position for p in ordered])
    if len(ordered) > 1:
        deltas = np.diff(positions, axis=0)
        steps = deltas @ normal
        if (np.any(steps <= 1e-4) or not np.allclose(steps, steps[0], atol=.02, rtol=.01) or
                not np.allclose(deltas, np.outer(steps, normal), atol=.02, rtol=0)):
            raise TemporalError('INCOMPLETE_OR_IRREGULAR_GRID')
    if len(ordered) * first.rows * first.columns * 4 > MAX_VOLUME_BYTES:
        raise TemporalError('RESOURCE_LIMIT')
    return ordered


def _build(planes, evidence):
    buckets = defaultdict(list)
    for plane in planes:
        key = plane.temporal if evidence == 'temporal_index' else plane.acquisition
        if key is None or key < 1:
            raise TemporalError('AMBIGUOUS_TEMPORAL_ORDER')
        buckets[key].append(plane)
    if not 2 <= len(buckets) <= MAX_PHASES:
        raise TemporalError('NO_REAL_TEMPORAL_GROUP' if len(buckets) < 2 else 'RESOURCE_LIMIT')
    keys = sorted(buckets)
    if keys != list(range(keys[0], keys[-1] + 1)):
        raise TemporalError('INCOMPLETE_TEMPORAL_GROUP')
    expected_counts = {p.declared_count for p in planes if p.declared_count is not None}
    if expected_counts and expected_counts != {len(buckets)}:
        raise TemporalError('INCOMPLETE_TEMPORAL_GROUP')
    volumes, clocks = [], []
    for key in keys:
        group = buckets[key]
        # Each time point is one complete source SeriesInstanceUID. Adjacent
        # stacks from other acquisitions cannot be stitched merely because their
        # temporal index and protocol match. A different complete UID per time
        # point is supported; cross-UID spatial concatenation is not inferred.
        if len({p.uid for p in group}) != 1:
            raise TemporalError('MIXED_SERIES_IN_PHASE')
        values = {p.timestamp for p in group}
        if evidence == 'dynamic_acquisition' and (None in values or len(values) != 1):
            raise TemporalError('AMBIGUOUS_TEMPORAL_TIME')
        clocks.append(min(values) if None not in values else None)
        volumes.append(_check_grid(group))
    reference = volumes[0]
    for volume in volumes[1:]:
        if (len(volume) != len(reference) or
                (volume[0].rows, volume[0].columns) != (reference[0].rows, reference[0].columns) or
                volume[0].identity != reference[0].identity or
                not np.allclose(volume[0].spacing, reference[0].spacing, atol=1e-5, rtol=0) or
                not np.allclose(volume[0].orientation, reference[0].orientation, atol=1e-5, rtol=0) or
                not np.allclose([p.position for p in volume], [p.position for p in reference], atol=.02, rtol=0)):
            raise TemporalError('MIXED_GEOMETRY_OR_IDENTITY')
    projection = any(p.projection for p in planes)
    if projection and len(reference) != 1:
        raise TemporalError('DERIVED_PROJECTION_IS_NOT_VOLUME')
    if len(reference) == 1 and not projection:
        raise TemporalError('NO_SPATIAL_VOLUME')
    if len(reference) > 1 and any(p.mono1 for p in planes):
        # Do not guess whether an inverse-polarity source represents a minimum
        # signal volume or an already transformed angiographic reconstruction.
        raise TemporalError('UNSUPPORTED_VOLUME_POLARITY')
    if evidence == 'temporal_index' and len(set(clocks)) == 1:
        # Enhanced MR may repeat the acquisition's global start on every frame.
        # The indices still order real time points; they do not measure seconds.
        clocks = [None] * len(clocks)
    if all(t is not None for t in clocks):
        if any(b <= a for a, b in zip(clocks, clocks[1:])):
            raise TemporalError('AMBIGUOUS_TEMPORAL_TIME')
        clocks = [round(t - clocks[0], 6) for t in clocks]
    else:
        resolutions = {p.temporal_resolution for p in planes}
        resolution = next(iter(resolutions)) if len(resolutions) == 1 else None
        clocks = ([round(i * resolution, 6) for i in range(len(keys))]
                  if resolution is not None and math.isfinite(resolution) and resolution > 0 else [None] * len(keys))
    return Group(tuple(Frame(v, k, t) for v, k, t in zip(volumes, keys, clocks)),
                 'projection2d' if projection else 'volume3d', evidence)


def discover(sources, *, anchor_identity=None):
    """sources are trusted resolver output {folder, uid}; never accept HTTP paths."""
    accepted, rejected, visited = [], Counter(), set()
    sources_by_folder = defaultdict(set)
    for source in sources:
        sources_by_folder[str(Path(source['folder']).resolve())].add(str(source['uid']))
    file_count = 0
    for folder, uids in sources_by_folder.items():
        root = Path(folder)
        try:
            files = root.rglob('*')
            for path in files:
                if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
                    continue
                file_count += 1
                if file_count > MAX_FILES:
                    raise TemporalError('RESOURCE_LIMIT')
                try:
                    ds = pydicom.dcmread(path, stop_before_pixels=True, specific_tags=_TAGS)
                except (pydicom.errors.InvalidDicomError, OSError, ValueError):
                    continue
                uid = str(getattr(ds, 'SeriesInstanceUID', ''))
                if uid not in uids:
                    continue
                if str(path) in visited:
                    continue
                visited.add(str(path))
                try:
                    accepted.extend(_planes(path, ds))
                except (TemporalError, ValueError, TypeError) as error:
                    rejected[error.code if isinstance(error, TemporalError) else 'INVALID_METADATA'] += 1
                    # Reject the whole UID if any of its required files are invalid.
                    rejected['uid:' + uid] += 1
                if len(accepted) > MAX_PLANES:
                    raise TemporalError('RESOURCE_LIMIT')
        except OSError:
            rejected['SOURCE_UNAVAILABLE'] += 1
    by_uid = defaultdict(list)
    for plane in accepted:
        by_uid[plane.uid].append(plane)
    valid = []
    for uid, planes in by_uid.items():
        if rejected.get('uid:' + uid):
            continue
        if len({p.identity for p in planes}) != 1:
            rejected['MIXED_GEOMETRY_OR_IDENTITY'] += 1
            continue
        if anchor_identity is not None and planes[0].identity[:3] != anchor_identity[:3]:
            continue
        valid.extend(planes)
    candidates = defaultdict(list)
    for plane in valid:
        if plane.temporal is not None:
            evidence = 'temporal_index'
        elif plane.frame_index is None and plane.dynamic and plane.timestamp is not None and plane.acquisition is not None:
            evidence = 'dynamic_acquisition'
        else:
            rejected['NO_REAL_TEMPORAL_GROUP'] += 1
            continue
        # A same-UID mismatch is rejected above; across UIDs identity remains separate.
        candidates[(plane.identity, plane.protocol, plane.stack, evidence)].append(plane)
    groups = []
    for (*_, evidence), planes in candidates.items():
        try:
            groups.append(_build(planes, evidence))
        except TemporalError as error:
            rejected[error.code] += 1
    return Discovery(groups, [{'code': code, 'count': count} for code, count in sorted(rejected.items())
                              if not code.startswith('uid:')])


def source_identity(folder, uid):
    """Read only the identity needed to anchor discovery to an already chosen case."""
    for count, path in enumerate(Path(folder).rglob('*')):
        if count >= MAX_FILES:
            break
        if not path.is_file() or path.is_symlink():
            continue
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True,
                                specific_tags=['PatientID', 'IssuerOfPatientID', 'StudyInstanceUID',
                                               'SeriesInstanceUID', 'FrameOfReferenceUID'])
            if str(getattr(ds, 'SeriesInstanceUID', '')) != str(uid):
                continue
            identity = tuple(str(getattr(ds, tag, '')) for tag in
                             ('PatientID', 'IssuerOfPatientID', 'StudyInstanceUID', 'FrameOfReferenceUID'))
            return identity if all(identity[i] for i in (0, 2, 3)) else None
        except (pydicom.errors.InvalidDicomError, OSError, ValueError):
            continue
    return None


def load_frame(group, index, *, cancelled=lambda: False):
    if not isinstance(index, int) or not 0 <= index < len(group.frames):
        raise TemporalError('INVALID_FRAME')
    planes = group.frames[index].planes
    first = planes[0]
    array = np.empty((len(planes), first.rows, first.columns), dtype=np.float32)
    for z, plane in enumerate(planes):
        if cancelled():
            raise TemporalError('CANCELLED')
        try:
            stat = Path(plane.path).stat()
            if (stat.st_size, stat.st_mtime_ns) != plane.file_stamp:
                raise TemporalError('SOURCE_CHANGED')
            if plane.frame_index is not None:
                # pydicom 3 indexes one frame; never decode a huge 4-D array as fallback.
                pixels_api = getattr(getattr(pydicom, 'pixels', None), 'pixel_array', None)
                if pixels_api is None:
                    raise TemporalError('INDEXED_MULTIFRAME_READER_REQUIRED')
                pixels = pixels_api(plane.path, index=plane.frame_index)
            else:
                pixels = pydicom.dcmread(plane.path).pixel_array
            if pixels.shape != (first.rows, first.columns):
                raise TemporalError('INVALID_PIXEL_FORMAT')
            np.multiply(pixels, plane.slope, out=array[z], casting='unsafe')
            array[z] += plane.intercept
            if not np.isfinite(array[z]).all():
                raise TemporalError('INVALID_PIXEL_VALUES')
        except TemporalError:
            raise
        except Exception:
            raise TemporalError('PIXEL_DECODE_FAILED') from None
    row, col = np.array(first.orientation[:3]), np.array(first.orientation[3:])
    normal = np.cross(row, col)
    if group.kind == 'projection2d':
        return FrameData(array[0], (first.spacing[1], first.spacing[0]), (0., 0.), (1., 0., 0., 1.), first.mono1)
    step = float(np.dot(np.array(planes[1].position) - np.array(first.position), normal))
    direction = tuple(np.column_stack((row, col, normal)).ravel())
    return FrameData(array, (first.spacing[1], first.spacing[0], step), first.position, direction, first.mono1)


def sample_values(data, limit=8192):
    flat = data.array.reshape(-1)
    sample = np.asarray(flat[::max(1, math.ceil(flat.size / limit))], dtype=np.float32)
    return np.concatenate((sample, np.array([flat.min(), flat.max()], dtype=np.float32)))


def shared_scale(samples):
    """One unchanged intensity transfer for every phase; no frame auto-windowing."""
    values = np.concatenate(samples)
    percentiles = (0, 1, 5, 25, 50, 75, 90, 95, 97, 98, 99, 99.5, 99.8, 99.9, 99.95, 99.99, 100)
    actual = np.percentile(values, percentiles)
    return {'hu': False, 'min': float(values.min()), 'max': float(values.max()),
            'percentis': dict(zip(percentiles, map(float, actual)))}

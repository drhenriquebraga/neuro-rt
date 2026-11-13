"""Header-only inventory inside explicitly ticket-authorized folders and one study."""
from pathlib import Path

import pydicom

from .nidus_temporal import MAX_FILES, TemporalError


def study_sources(folders, identity):
    """Return private sources; neither paths nor identifying headers leave this helper."""
    roots = sorted({Path(folder).resolve() for folder in folders}, key=lambda p: len(p.parts))
    selected = []
    for root in roots:
        if not any(root.is_relative_to(parent) for parent in selected):
            selected.append(root)
    seen, sources, entries = set(), [], 0
    tags = ['PatientID', 'IssuerOfPatientID', 'StudyInstanceUID', 'SeriesInstanceUID', 'Modality']
    for root in selected:
        try:
            for path in root.rglob('*'):
                entries += 1
                if entries > MAX_FILES * 4:
                    raise TemporalError('RESOURCE_LIMIT')
                if (not path.is_file() or path.is_symlink() or
                        not path.resolve().is_relative_to(root)):
                    continue
                if len(seen) >= MAX_FILES:
                    raise TemporalError('RESOURCE_LIMIT')
                resolved = str(path.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)
                try:
                    ds = pydicom.dcmread(path, stop_before_pixels=True, specific_tags=tags)
                except (OSError, ValueError, pydicom.errors.InvalidDicomError):
                    continue
                found = tuple(str(getattr(ds, tag, '')) for tag in tags[:3])
                uid = str(getattr(ds, 'SeriesInstanceUID', ''))
                if found != identity[:3] or str(getattr(ds, 'Modality', '')) != 'MR' or not uid:
                    continue
                source = {'folder': str(root), 'uid': uid}
                if source not in sources:
                    sources.append(source)
        except OSError:
            raise TemporalError('SOURCE_UNAVAILABLE') from None
    return sources

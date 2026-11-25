"""Render input previews using only a generated multi-series calibration phantom."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pydicom
from pydicom.uid import CTImageStorage, generate_uid
# Windows' embedded Python does not add the invoked script directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from synthetic_dicom import make_series


def prepare(root, host, work):
    sys.path.insert(0, str(root))
    from integration.host_imports import prepare_host_imports
    prepare_host_imports(host)
    import radai_varrer
    import radai_dicom
    import radai_thumbnail
    from integration.radai_neuro_screen import pagina_estudo

    for category in ('anatomia', 'glioma', 'metastasis', 'meningioma'):
        (work / (category + '.html')).write_text(pagina_estudo(category, None), encoding='utf-8')

    source = work / 'phantom'
    study, frame = generate_uid(), generate_uid()
    y, x = np.mgrid[-1:1:224j, -1:1:224j]
    descriptions = {}
    for sequence_index, role in enumerate(('T1', 'T1c', 'T2', 'CT')):
        folder = source / role
        uid, _ = make_series(folder, modality='CT' if role == 'CT' else 'MR', slices=7)
        descriptions[uid] = role
        for index, file in enumerate(sorted(folder.glob('*.dcm'))):
            ds = pydicom.dcmread(file)
            if role == 'CT':
                ds.SOPClassUID = ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
            ds.StudyInstanceUID, ds.FrameOfReferenceUID = study, frame
            ds.SeriesDescription = 'Fantoma ' + role
            ds.SeriesNumber = sequence_index + 1
            ds.PixelSpacing = [1, 1]
            ds.SliceThickness = 2
            ds.ProtocolName = 'Protocolo fantoma'
            if role != 'CT':
                ds.MagneticFieldStrength = 3
                ds.EchoTime = 12
            ds.Rows, ds.Columns = x.shape
            ds.WindowCenter, ds.WindowWidth = 600, 1200
            pixels = np.zeros(x.shape, dtype=np.uint16)
            radius = 0.89 - abs(index - 3) * 0.05
            pixels[x*x + y*y < radius**2] = 1060
            pixels[x*x + y*y < (radius - .04)**2] = 200 + 110*sequence_index
            for k, (cx, cy) in enumerate(((-.30, -.28), (.30, -.28), (0., .24))):
                insert = (x-cx)**2 + (y-cy)**2 < (.145 + index*.011)**2
                pixels[insert] = (450, 800, 1200)[(k+sequence_index)%3]
            ds.PixelData = pixels.tobytes()
            ds.save_as(file, enforce_file_format=True)

    series = radai_dicom.varrer(str(source))['series']
    tickets = radai_thumbnail.registrar_series(str(source), series)
    rows = []
    for s in sorted(series, key=lambda item: int(item['numero'])):
        ticket = tickets[s['uid']]
        role = descriptions[s['uid']]
        row = radai_varrer.linha_da_serie(str(source), s, ticket)
        from integration.default_host_services import bindings_for_host
        resolved = bindings_for_host({})['resolve_series_ticket'](ticket)
        rows.append(dict(row, role=role, preview_header=resolved['preview_header']))
        with patch.object(radai_thumbnail, '_pasta_cache', return_value=''):
            png, metadata = radai_thumbnail.png_central(ticket)
        assert png[:8] == b'\x89PNG\r\n\x1a\n' and metadata['cortes'] == 7
        (work / (ticket + '.png')).write_bytes(png)
        for index in range(metadata['cortes']):
            png, _ = radai_thumbnail.png(ticket, index, janela='mediastino' if role == 'CT' else 'auto', lado=512)
            assert png[:8] == b'\x89PNG\r\n\x1a\n'
            (work / f'{ticket}-{index}.png').write_bytes(png)
    assert len(rows) == 4
    (work / 'phantom.json').write_text(json.dumps(rows), encoding='utf-8')


if __name__ == '__main__':
    prepare(*(Path(arg).resolve() for arg in sys.argv[1:]))



"""Prova sintética da publicação, executada uma vez no runtime do host."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from neuro_rt.export import export

job, host = Path(sys.argv[1]), Path(sys.argv[2])
first = export(job, host)['rtstruct']['source_path']
original_bytes = Path(first).read_bytes()
second = export(job, host)['rtstruct']['source_path']
assert first != second
assert Path(first).read_bytes() == original_bytes

import pydicom
origin = Path(json.loads((job/'manifest.json').read_text())['source']['input_path'])
slice_path = sorted(origin.glob('*.dcm'))[0]
changed = pydicom.dcmread(slice_path)
changed.FrameOfReferenceUID = pydicom.uid.generate_uid()
changed.save_as(slice_path, enforce_file_format=True)
try:
    export(job, host)
except ValueError:
    pass
else:
    raise AssertionError('Série de origem alterada não foi recusada.')
assert len(list(origin.glob('RS_NeuroRT_*.dcm'))) == 2
print('Publicação exclusiva, preservação do arquivo anterior e alteração da origem conferidas.')

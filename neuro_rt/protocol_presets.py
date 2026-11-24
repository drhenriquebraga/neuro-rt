"""Workstation-wide NEURO preferences. Never serialize a DICOM ticket or binding."""
from contextlib import contextmanager
import json
from pathlib import Path
import re
import threading
import uuid

from .result_store import atomic_json
from .study_protocols import validate_delivery_plan

SCHEMA = 'neuro-rt/protocols/1'


class ProtocolPresets:
    def __init__(self, catalog, data_dir, storage=None):
        self.catalog = catalog
        self.path = Path(data_dir) / 'config' / 'protocolos_neuro.json'
        self.storage = storage or self._local_storage
        self.lock = threading.RLock()

    @contextmanager
    def _local_storage(self):
        with self.lock:
            yield self.path

    def _record(self, row, ident):
        if (not isinstance(row,dict) or set(row) - {'id','name','modality','plan'}
                or not isinstance(ident,str) or not re.fullmatch('p[a-f0-9]{32}', ident)):
            raise ValueError('Protocolo NEURO inválido.')
        name = row.get('name')
        if not isinstance(name,str) or not 1 <= len(name.strip()) <= 80 or not name.strip().isprintable():
            raise ValueError('Informe um nome de até 80 caracteres para o protocolo.')
        modality = row.get('modality')
        return {'id':ident, 'name':name.strip(), 'modality':modality,
                'plan': validate_delivery_plan(row.get('plan'),modality,self.catalog)}

    def _read(self, path):
        if not path.is_file():
            return []
        if path.stat().st_size > 2*1024*1024:
            raise ValueError('O arquivo de protocolos NEURO excede o limite.')
        doc = json.loads(path.read_text(encoding='utf-8-sig'))
        if (not isinstance(doc,dict) or set(doc) != {'schema','protocols'} or doc.get('schema') != SCHEMA
                or not isinstance(doc.get('protocols'),list) or len(doc['protocols']) > 200
                or not all(isinstance(row,dict) for row in doc['protocols'])):
            raise ValueError('Arquivo de protocolos NEURO inválido.')
        return doc['protocols']

    def list(self, modality=None):
        with self.storage() as path:
            rows = self._read(path)
        result = []
        for row in rows:
            if modality is None or row.get('modality') == modality:
                try:
                    result.append(self._record(row,row.get('id')))
                except ValueError:
                    # An older station may restore preferences from a newer catalog.
                    # Keep these records on disk without presenting an unusable plan.
                    continue
        return result

    def save(self, row):
        if not isinstance(row,dict):
            raise ValueError('Protocolo NEURO inválido.')
        ident = row.get('id') or 'p' + uuid.uuid4().hex
        record = self._record(row,ident)
        with self.storage() as path:
            rows = self._read(path)
            existing = False
            new = []
            for previous in rows:
                if previous.get('id') == ident:
                    existing = True
                    new.append(record)
                elif (previous.get('modality') == record['modality']
                      and str(previous.get('name','')).casefold() == record['name'].casefold()):
                    if not row.get('id') and previous.get('plan') == record['plan']:
                        return
                    raise ValueError('Já existe um protocolo NEURO com esse nome.')
                else:
                    new.append(previous)
            if not existing:
                if row.get('id'):
                    raise KeyError('Protocolo NEURO não encontrado.')
                if len(new) >= 200:
                    raise ValueError('O limite é de 200 protocolos NEURO.')
                new.append(record)
            doc = {'schema':SCHEMA, 'protocols':new}
            if len(json.dumps(doc,ensure_ascii=False,indent=2).encode('utf-8')) > 2*1024*1024:
                raise ValueError('O arquivo de protocolos NEURO excede o limite.')
            atomic_json(path,doc)

    def delete(self, ident):
        with self.storage() as path:
            rows = self._read(path)
            kept = [p for p in rows if p.get('id') != ident]
            if len(kept) == len(rows):
                raise KeyError('Protocolo NEURO não encontrado.')
            atomic_json(path,{'schema':SCHEMA, 'protocols':kept})

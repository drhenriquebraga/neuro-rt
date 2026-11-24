"""Read a persisted NEURO revision through the native Local Suite reconstruction API."""
import hashlib
import json
import re
import shutil
import threading
from collections import OrderedDict
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

from neuro_rt.contracts import validate_identifier
from neuro_rt.result_store import sha256_file

PLANES = ('axial', 'coronal', 'sagittal')


def split_ticket(ticket):
    prefix, ident, revision = ticket.split(':')
    validate_identifier(ident, 'study_id')
    if prefix != 'neuro' or not re.fullmatch(r'[1-9][0-9]{0,8}', revision):
        raise ValueError('Revisão inválida.')
    return ident, int(revision)


def _model_names(ids):
    names = {'anatomy_synthseg': 'SynthSeg', 'anatomy_cerebra_ants': 'CerebrA / ANTs', 'cranio_buti': 'Buti'}
    return ' + '.join(names.get(m, m) for m in ids)


class NeuroReview:
    def __init__(self, service, authorize):
        self.service = service
        self.authorize = authorize
        self._scenes = OrderedDict()
        self._bounds = {}
        self._lock = threading.Lock()

    @property
    def store(self):
        return self.service.studies.store

    def rows(self, limit, published=()):
        records = self.store.iter_manifests(all_revisions=True)
        rows = []
        for item in reversed(list(records)):
            if not any(a['kind'] in ('view', 'mask') for a in item.artifacts):
                continue
            if item.export_receipt and item.export_receipt.published_file:
                rt = Path(item.export_receipt.published_file)
                if (rt.parent, item.reference.series_uid) in published and rt.is_file():
                    continue
            ident, rev = item.study_id, item.revision
            models = _model_names(item.requested_model_ids)
            rows.append(dict(bilhete=f'neuro:{ident}:{rev}', uid8=f'{ident} · r{rev}', pid='',
                             revisao_neuro=True, desc=models, modalidade=item.reference.modality,
                             detalhes_locais=dict(modalidade=item.reference.modality,
                                 tasks=[f'{models} · {ident} · r{rev}'], cortes=len(item.reference.sop_instance_uids) or None),
                             date='', estado='ok', estruturas=sum(len(m.masks) for m in item.results),
                             quando='', secs=0))
            if len(rows) >= limit:
                break
        return rows

    def _rebuild(self, ident, manifest, records):
        """Recreate display files only if the archived masks have their own verified reference."""
        from neuro_rt.build_study_views import build_study_views
        job_root = (self.store.data_dir / 'jobs' / ident).resolve()
        if not job_root.is_relative_to((self.store.data_dir / 'jobs').resolve()):
            raise ValueError('Referência privada inválida.')
        ref = manifest.reference
        source = None
        candidates = [job_root] + sorted((job_root/'attempts').glob('[0-9]*'))
        for job in candidates:
            try:
                if not job.resolve().is_relative_to(job_root):
                    continue
                cache = json.loads((job/'preparation-cache.json').read_text(encoding='utf-8'))
                original = job/'inputs/reference.nii.gz'
                desc = cache['series_index'][ref.ticket]
                if (not original.resolve().is_relative_to(job) or desc['series_uid'] != ref.series_uid
                        or desc['study_key'] != ref.study_key or desc['subject_key'] != ref.subject_key
                        or desc.get('frame_of_reference_uid','') != ref.frame_of_reference_uid
                        or set(desc.get('sop_instance_uids', [])) != set(ref.sop_instance_uids)
                        or Path(cache['authorized_inputs'][ref.ticket]).resolve() != original.resolve()):
                    continue
                if sha256_file(original) == cache['input_hashes'][ref.ticket]:
                    source = original, cache['input_hashes'][ref.ticket]
                    break
            except (KeyError, OSError, ValueError):
                continue
        if not source:
            raise ValueError('A revisão tem máscaras, mas a imagem de referência verificada está indisponível.')
        tmp = TemporaryDirectory(prefix='neuro-revisao-')
        try:
            local = Path(tmp.name)
            (local/'inputs').mkdir()
            shutil.copyfile(source[0], local/'inputs/reference.nii.gz')
            if sha256_file(local/'inputs/reference.nii.gz') != source[1]:
                raise ValueError('A imagem de referência mudou.')
            by_path = {a['path']: a for a in records if a['kind'] == 'mask'}
            checked_masks = self.store.resolve_artifacts(ident, [a['artifact_id'] for a in by_path.values()])
            data = manifest.to_dict()
            for result in data['results']:
                for mask in result['masks']:
                    row = by_path[mask['path']]
                    checked = checked_masks[row['artifact_id']]
                    if checked.revision != manifest.revision:
                        raise ValueError('Máscara de outra revisão.')
                    target = local/checked.path.name
                    shutil.copyfile(checked.path, target)
                    if sha256_file(target) != row['sha256']:
                        raise ValueError('A máscara da revisão mudou.')
                    mask['path'] = str(target)
            data['artifacts'] = []
            (local/'study-manifest.json').write_text(json.dumps(data),encoding='utf-8')
            scene = build_study_views(local,self.service.settings.host_app)
            paths = {f.name:f for f in (local/'views').iterdir() if f.is_file()}
            return tmp, scene, paths
        except BaseException:
            tmp.cleanup()
            raise

    def _revision(self, ticket):
        ident, rev = split_ticket(ticket)
        with self._lock:
            if ticket in self._scenes:
                self._scenes.move_to_end(ticket)
                return self._scenes[ticket]
            m = self.store.load_manifest(ident, rev)
            records = list(m.artifacts)
            assets = {a['logical_name']:a for a in records if a.get('logical_name')}
            temp = None
            if 'view.json' in assets:
                checked = self.store.resolve_artifact(ident, assets['view.json']['artifact_id'])
                if checked.revision != rev:
                    raise ValueError('Cena de outra revisão.')
                scene = json.loads(checked.path.read_bytes())
                if scene.get('schema') != 'neuro-rt/view/2' or scene.get('orientation') != 'LPS':
                    raise ValueError('Cena neuroanatômica incompatível.')
            else:
                temp, scene, assets = self._rebuild(ident,m,records)
            rois = {r.get('roi_name') or r['label']: r for r in scene['rois']}
            value = m, scene, rois, assets, temp
            self._scenes[ticket] = value
            if len(self._scenes) > 4:
                expired, _ = self._scenes.popitem(last=False)
                self._bounds.pop(expired, None)
            return value

    def _bytes(self, ticket, name):
        m, _, _, assets, tmp = self._revision(ticket)
        row = assets[name]
        if tmp:
            return row.read_bytes()
        # load_manifest checked these immutable paths. Recheck containment
        # and the digest of the exact bytes returned, even for cached scenes.
        directory = (self.store.root / m.study_id / 'revisions' / str(m.revision) / 'artifacts')
        path = Path(row['path']).resolve()
        if (directory.resolve() != directory or path.parent != directory or
                not path.name.startswith(row['artifact_id'] + '.')):
            raise ValueError('Artefato fora da revisão.')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Artefato da revisão alterado.')
        return data

    def _file(self, m):
        return {'arquivo': 'neuro', 'nome': _model_names(m.requested_model_ids) + f' · r{m.revision}',
                'conjunto': 'neuro', 'plugin': True}

    def state(self, ticket):
        m, scene, _, _, _ = self._revision(ticket)
        return dict(segmentada=True, conjuntos=[self._file(m)], forma=[scene['planes'][p]['count'] for p in PLANES],
                    cranial=1, historico_planar=True, modalidade=m.reference.modality, estudo_3d=[])

    def structures(self, ticket, rs=''):
        if rs not in ('','neuro'):
            raise ValueError('Conjunto inválido.')
        m, scene, rois, _, _ = self._revision(ticket)
        boxes = self.bounds(ticket, rois)
        return dict(rs='neuro', arquivos=[self._file(m)], estruturas=[
            dict(nome=name, cor=r['color'], opacidade=r.get('opacity',.7), casca=False, achado=False,
                 vaso=False, osso=False, caixa=boxes.get(name)) for name,r in rois.items()],
            caixa=boxes.get(None,scene['bounds']),
            eixos=['esq','post','sup'], camadas=[], marcar_ate=45, sem_segmentacao=False, erro='')

    def bounds(self, ticket, rois):
        import numpy as np
        from struct import unpack_from
        with self._lock:
            if ticket in self._bounds:
                return self._bounds[ticket]
        boxes = {}
        # STL coordinates already use the reference LPS millimetres. Frame the
        # surfaces themselves just as the DICOM reconstructor does.
        face = np.dtype([('normal','<3f4'),('vertices','<f4',(3,3)),('attribute','<u2')])
        for name, roi in rois.items():
            if not roi.get('mesh'):
                continue
            data = self.mesh(ticket, name)
            count, = unpack_from('<I',data,80)
            if len(data) != 84+50*count:
                raise ValueError('Malha inválida.')
            if count:
                vertices = np.frombuffer(data,dtype=face,offset=84)['vertices']
                boxes[name] = [vertices.min(axis=(0,1)).tolist(),vertices.max(axis=(0,1)).tolist()]
        if boxes:
            limits = np.asarray(list(boxes.values()))
            boxes[None] = [limits[:,0].min(axis=0).tolist(),limits[:,1].max(axis=0).tolist()]
        with self._lock:
            if ticket in self._scenes:
                self._bounds[ticket] = boxes
        return boxes

    def plane(self, ticket, axis, pos, overlay, names):
        if axis not in (0,1,2):
            raise ValueError('Plano inválido.')
        m, scene, rois, _, _ = self._revision(ticket)
        plane = scene['planes'][PLANES[axis]]
        index = round(max(0.,min(1.,pos))*(plane['count']-1))
        allowed = {roi['id'] for name, roi in rois.items() if overlay and (names is None or name in names)}
        root = ET.fromstring(self._bytes(ticket,plane['slices'][index]))
        # Native study SVGs consist of an embedded grayscale PNG and ROI paths.
        for elem in root.iter():
            if elem.tag.rsplit('}',1)[-1] not in ('svg','image','path','g'):
                raise ValueError('Corte armazenado inválido.')
            for attr, val in elem.attrib.items():
                if attr.rsplit('}',1)[-1].startswith('on') or (attr.endswith('href') and not val.startswith('data:image/png;base64,')):
                    raise ValueError('Imagem do corte inválida.')
        for group in list(root):
            if group.get('data-roi') is not None and group.get('data-roi') not in allowed:
                root.remove(group)
        return ET.tostring(root,encoding='utf-8')

    def mesh(self, ticket, name):
        _, _, rois, _, _ = self._revision(ticket)
        mesh = rois[name].get('mesh')
        if not mesh:
            raise KeyError(name)
        return self._bytes(ticket, mesh)

    def cloud(self, ticket, names):
        from struct import unpack_from
        _, _, rois, _, _ = self._revision(ticket)
        items=[]
        for name in (list(rois)[:24] if names is None else names):
            if name not in rois or not rois[name].get('mesh'):
                continue
            data = self.mesh(ticket, name)
            count, = unpack_from('<I',data,80)
            if len(data) != 84+50*count:
                raise ValueError('Malha inválida.')
            points, normals = [], []
            for i in range(0,count,max(1,(count+2999)//3000)):
                normal_x,normal_y,normal_z,x,y,z = unpack_from('<6f',data,84+i*50)
                normals.append([normal_x,normal_y,normal_z]); points.append([x,y,z])
            items.append(dict(nome=name,cor=rois[name]['color'],pontos=points,normais=normals,centro_mm=[0,0,0]))
        return dict(itens=items,lps=True,erro='')


"""Stable model/class ROI identity; translated display labels never become keys."""
from dataclasses import dataclass, replace
import hashlib
import json

from .model_registry import get_model_spec


@dataclass(frozen=True)
class RoiIdentity:
    roi_id: str
    roi_name: str
    description: str
    color: tuple

    @property
    def writer_key(self):
        # The host appends its own _ai provenance suffix, within 16 characters.
        return self.roi_name[:-3]


def make_roi_identity(model_id, class_id, revision, *, catalog=None):
    spec = get_model_spec(model_id) if catalog is None else catalog[model_id]
    if spec.get('id') != model_id:
        raise ValueError('Identidade de modelo divergente do catálogo autorizado.')
    if not any(type(c['class_id']) is type(class_id) and c['class_id'] == class_id
               for c in spec['classes']):
        raise ValueError('Classe fora do catálogo verificado.')
    if spec['catalog_state'] not in ('distributed', 'verified'):
        raise ValueError('Modelo candidato não permite publicar contornos.')
    key = json.dumps([model_id, class_id], ensure_ascii=True, separators=(',', ':'))
    digest = hashlib.sha256(key.encode()).hexdigest()
    short = 'N' + digest[:12]
    description = (f'Sugestao nao aprovada. NeuroRT / modelo {model_id} / classe {class_id} '
                   f'/ revisao {revision} / artefato {spec["revision"]}. '
                   'Mascara na referencia original; sem CTV automatico ou registro RM-TC.')
    return RoiIdentity('roi-' + digest, short + '_ai', description,
                       tuple(64 + int(digest[i:i+2], 16) % 192 for i in (0, 2, 4)))


def collect_reference_masks(manifest, *, catalog=None):
    collection, seen = [], set()
    for result in manifest.results:
        if result.status not in ('completed', 'partial'):
            continue
        for mask in result.masks:
            if mask.space != 'reference':
                raise ValueError('A exportação exige máscara restaurada à referência.')
            identity = make_roi_identity(result.model_id, mask.class_id, manifest.revision,
                                         catalog=catalog)
            provenance = json.dumps({'versions': result.versions, 'hashes': result.hashes},
                                    sort_keys=True, ensure_ascii=True)
            identity = replace(identity, description=identity.description + ' ' + provenance)
            if identity.roi_name in seen:
                raise ValueError('Identidade de ROI duplicada ou colidida.')
            seen.add(identity.roi_name)
            collection.append((identity, mask))
    return collection

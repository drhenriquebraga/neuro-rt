"""Offline assets and common binary-mask boundary for scientific workers."""
from ..scientific_io import read_image
from dataclasses import dataclass, replace
import hashlib
from ..integrity import sha256_file
import json
from pathlib import Path

from .base import PreparedInputs
from ..contracts import validate_model_result
from ..geometry_pipeline import prepare_model_inputs, restore_masks
from ..model_paths import resolve_model_folder
from ..study_types import ContractMessage, MaskArtifact, ModelResult


def asset_spec(model_id):
    root = Path(__file__).resolve().parents[2]
    path = root / 'catalog/model_assets_v1_manifest.json'
    if not path.is_file():
        # Development checkout keeps the audited source in scripts/. Installed
        # releases include only the canonical catalog file, never a checkout path.
        path = root / 'scripts/model_assets_v1_manifest.json'
    return json.loads(path.read_text(encoding='utf-8'))['models'][model_id]


def verified_assets(context):
    spec = asset_spec(context.model_spec['id'])
    folder = resolve_model_folder(context.models_dir, context.model_spec['id'],
                                  context.model_spec['revision'],
                                  allow_legacy=context.allow_legacy_models)
    hashes = {}
    for relative, entry in spec['files'].items():
        path = folder / relative
        digest = sha256_file(path)
        if path.stat().st_size != entry['size'] or digest != entry['sha256']:
            raise ValueError(f'Artefato local alterado/corrompido: {relative}')
        hashes[relative] = digest
    return folder, hashes


@dataclass(frozen=True)
class ScientificPrediction:
    prepared: PreparedInputs
    masks: list
    transformations: list
    versions: dict
    hashes: dict


class ScientificAdapter:
    roles = ()
    cpu_only = False

    def prepare(self, context):
        if context.device not in ('cpu', 'cuda'):
            raise ValueError('O dispositivo deve estar resolvido em cpu ou cuda.')
        if self.cpu_only and context.device != 'cpu':
            raise ValueError('Este adaptador está habilitado somente em CPU.')
        if [c['role'] for c in context.model_spec['channels']] != list(self.roles):
            raise ValueError('Ordem dos canais diverge do contrato publicado.')
        return prepare_model_inputs(context.bindings, context.reference, context.model_spec, context)

    def normalize_result(self, raw, context):
        import numpy as np
        import SimpleITK as sitk
        context.checkpoint('restoring', 0.)
        result = ModelResult(context.model_spec['id'], 'completed', raw.masks,
                             transformations=raw.prepared.transform_chain + raw.transformations,
                             versions=raw.versions, hashes=raw.hashes)
        before = {m.class_id: int(np.count_nonzero(sitk.GetArrayFromImage(read_image(m.path))))
                  for m in raw.masks}
        restored = restore_masks(result, raw.prepared, context.reference)
        masks, warnings, counts = [], [], []
        for mask in restored:
            after = int(np.count_nonzero(sitk.GetArrayFromImage(read_image(mask.path))))
            record = {'model_id': result.model_id, 'class_id': mask.class_id,
                      'working_voxels': before[mask.class_id], 'reference_voxels': after,
                      'interpolation': 'nearest_neighbor'}
            counts.append(record)
            if before[mask.class_id] and not after:
                warnings.append(ContractMessage('class_lost_on_reference_grid',
                    'Classe não vazia ficou vazia ao retornar à grade de referência.', record))
            if after:
                masks.append(replace(mask, provenance={**mask.provenance, 'restoration_counts': record}))
        # Retain counts even for originally empty classes; never invent a voxel.
        result = replace(result, status='completed' if masks else 'empty', masks=masks,
                         geometry=context.reference.geometry, warnings=warnings,
                         transformations=result.transformations + [{
                             'operation': 'reference_grid_class_counts', 'classes': counts}])
        context.checkpoint('restoring', 1.)
        return validate_model_result(result, context.model_spec)


def binary_masks(arrays, affine, classes, context):
    import nibabel as nib
    import numpy as np
    import SimpleITK as sitk
    from ..imaging import geometry
    affine = np.asarray(affine)
    if (affine.shape != (4, 4) or not np.isfinite(affine).all()
            or abs(np.linalg.det(affine[:3, :3])) < 1e-12):
        raise ValueError('Transformação de saída inválida ou não finita.')
    folder = Path(context.job_dir) / 'scientific_masks'
    folder.mkdir(parents=True, exist_ok=True)
    masks = []
    for index, (array, class_id) in enumerate(zip(arrays, classes, strict=True)):
        array = np.asarray(array)
        if array.ndim != 3 or not np.isfinite(array).all() or not np.isin(array, [0, 1]).all():
            raise ValueError('Saída de classe deve ser volume binário 3D finito.')
        path = folder / f'{index}.nii.gz'
        nib.save(nib.Nifti1Image(array.astype(np.uint8), affine), path)
        masks.append(MaskArtifact(context.model_spec['id'], class_id, str(path),
                                  geometry(read_image(str(path))), 'working',
                                  {'adapter': context.model_spec['adapter_id']}))
    return masks


def label_masks(labels, affine, context):
    import numpy as np
    table = asset_spec(context.model_spec['id'])['contract']['classes']
    if not np.isfinite(labels).all() or not np.isin(labels, [0, *[c['value'] for c in table]]).all():
        raise ValueError('Atlas/segmentação contém labels inválidos ou não finitos.')
    return binary_masks((labels == c['value'] for c in table), affine,
                        [c['class_id'] for c in table], context)

"""Bridge to the verified single-channel Raidionics worker, without a new engine."""
from dataclasses import dataclass, replace
from pathlib import Path

from .base import ModelRunContext, PreparedInputs
from ..contracts import read_result_v1, validate_model_result
from ..geometry_pipeline import prepare_model_inputs, restore_masks
from ..study_types import ModelResult


@dataclass(frozen=True)
class RawPrediction:
    manifest: dict
    job_dir: Path
    prepared: PreparedInputs


class RaidionicsAdapter:
    def prepare(self, context: ModelRunContext) -> PreparedInputs:
        if context.device not in ('cpu', 'cuda'):
            raise ValueError('O dispositivo deve estar resolvido em cpu ou cuda.')
        if len(context.model_spec['channels']) != 1:
            raise ValueError('Este adaptador Raidionics exige um canal; multissequência ainda não habilitada.')
        return prepare_model_inputs(context.bindings, context.reference, context.model_spec, context)

    def predict(self, prepared: PreparedInputs, context: ModelRunContext) -> RawPrediction:
        # This method runs inside the orchestrator's private worker process.
        # Cancellation during native code requires that process to be terminated.
        from ..worker import run_job
        context.checkpoint('running', 0.)
        if len(prepared.channel_paths) != 1 or context.device not in ('cpu', 'cuda'):
            raise ValueError('Canal ou dispositivo não corresponde ao adaptador Raidionics.')
        job_dir = Path(context.job_dir).resolve() / 'raidionics'
        job_dir.mkdir(parents=True, exist_ok=False)
        manifest = run_job({'model': context.model_spec['id'],
                            'input_path': prepared.channel_paths[0],
                            'series_uid': '', 'device': context.device,
                            'explicit_request': True, 'export_rtstruct': False},
                           job_dir, context.models_dir,
                           allow_legacy_models=context.allow_legacy_models)
        context.checkpoint('running', 1.)
        return RawPrediction(manifest, job_dir, prepared)

    def normalize_result(self, raw: RawPrediction, context: ModelRunContext) -> ModelResult:
        context.checkpoint('restoring', 0.)
        result = read_result_v1(raw.manifest, context.model_spec)
        resolved = []
        for mask in result.masks:
            path = (raw.job_dir / mask.path).resolve()
            if not path.is_relative_to(raw.job_dir.resolve()):
                raise ValueError('Caminho de máscara fora da pasta privada do motor.')
            resolved.append(replace(mask, path=str(path), space='working'))
        result = replace(result, masks=resolved)
        masks = restore_masks(result, raw.prepared, context.reference)
        result = replace(result, masks=masks, geometry=raw.prepared.working_geometry,
                         transformations=raw.prepared.transform_chain + [{
                             'operation': 'raidionics_published_preprocessing_and_reconstruction',
                             'backend': 'raidionicsseg', 'output_space': 'working',
                             'details': 'Backend original; recorte/normalização/retorno internos ao motor.'}])
        context.checkpoint('restoring', 1.)
        return validate_model_result(result, context.model_spec)

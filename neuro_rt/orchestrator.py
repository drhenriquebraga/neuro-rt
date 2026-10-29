"""Sequential study execution; the caller owns the host lease and worker process."""
import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .adapters.base import ModelRunContext, RunCancelled
from .contracts import validate_model_result
from .study_types import ContractMessage, ModelResult, SeriesDescriptor, StudyItem, StudyManifest


@dataclass(frozen=True)
class ExecutionPlan:
    study_id: str
    reference: str
    model_steps: tuple[dict, ...]
    selected_model_ids: tuple[str, ...]
    bindings_by_model: dict


@dataclass
class StudyRunContext:
    reference: SeriesDescriptor
    series_index: dict
    authorized_inputs: dict
    job_dir: Path
    models_dir: Path
    effective_device: str
    device_preference: str
    plugin_version: str
    request_id: str
    revision: int = 1
    cancel_requested: Callable[[], bool] = lambda: False
    on_event: Callable[[dict], None] = lambda event: None
    error_sink: Callable[[str, Exception], None] = lambda model, error: None
    source_to_reference: dict = field(default_factory=dict)
    execution_keys: dict = field(default_factory=dict)
    previous_results: dict = field(default_factory=dict)


def build_study_plan(study, catalog) -> ExecutionPlan:
    if not isinstance(study, StudyItem):
        raise ValueError('O estudo precisa passar pelo contrato de entrada v2.')
    if not study.model_ids or len(set(study.model_ids)) != len(study.model_ids):
        raise ValueError('Selecione modelos distintos para o estudo.')
    steps = []
    for model_id in study.model_ids:
        spec = catalog.get(model_id)
        if (not isinstance(spec, dict) or spec.get('id') != model_id
                or spec.get('catalog_state') not in ('distributed', 'verified')):
            raise ValueError('Modelo indisponível para execução nesta release.')
        if model_id not in study.bindings_by_model:
            raise ValueError('Modelo sem associação de entradas.')
        steps.append(copy.deepcopy(spec))
    return ExecutionPlan(study.study_id, study.reference, tuple(steps),
                         tuple(study.model_ids), copy.deepcopy(study.bindings_by_model))


def run_study(plan, context, runner) -> StudyManifest:
    """Run model boundaries in order, retaining independent successful outputs.

    ``runner(spec, ModelRunContext)`` is an internal callable: in production it
    dispatches the authorized model runtime/process, never a client-provided name.
    D03 adapters validate physical geometry; export/publication is a later stage.
    """
    if context.reference.ticket != plan.reference:
        raise ValueError('A referência do contexto não corresponde ao estudo.')
    if context.effective_device not in ('cpu', 'cuda'):
        raise ValueError('Dispositivo efetivo precisa estar resolvido antes da execução.')
    if context.device_preference not in ('auto', 'cpu', 'cuda'):
        raise ValueError('Preferência de processamento inválida.')
    if context.device_preference == 'cpu' and context.effective_device != 'cpu':
        raise ValueError('CPU estrita não permite executar na GPU.')
    if context.device_preference == 'cuda' and context.effective_device != 'cuda':
        raise ValueError('GPU estrita não permite fallback para CPU.')
    job_dir = Path(context.job_dir).resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    results = []
    cancelled = False
    for step, spec in enumerate(plan.model_steps):
        model_id = spec['id']
        if cancelled or context.cancel_requested():
            cancelled = True
            results.append(ModelResult(model_id, 'cancelled'))
            continue
        context.on_event({'study_id': plan.study_id, 'model_id': model_id,
                          'status': 'preparing', 'step': step, 'steps': len(plan.model_steps)})
        model_dir = (job_dir / 'models' / model_id).resolve()
        if not model_dir.is_relative_to(job_dir):
            raise ValueError('Identificador de modelo fora da pasta privada do estudo.')
        def progress(stage, fraction, current=model_id):
            context.on_event({'study_id': plan.study_id, 'model_id': current,
                              'status': stage, 'fraction': fraction})
        model_context = ModelRunContext(
            spec, plan.bindings_by_model[model_id], context.reference,
            context.series_index, context.authorized_inputs, model_dir,
            Path(context.models_dir), context.effective_device,
            context.cancel_requested, progress, context.source_to_reference)
        model_context.study_id = plan.study_id
        try:
            previous = context.previous_results.get(model_id)
            if (isinstance(previous, dict) and context.execution_keys.get(model_id)
                    and previous.get('execution_key') == context.execution_keys[model_id]):
                cached = validate_model_result(previous.get('result'), spec)
                result = cached if cached.status in ('completed', 'empty') else runner(spec, model_context)
            else:
                result = runner(spec, model_context)
            result = validate_model_result(result, spec)
            if result.status not in ('completed', 'empty', 'partial', 'failed', 'interrupted', 'cancelled'):
                raise ValueError('O motor não entregou um estado terminal.')
            if result.status == 'cancelled':
                cancelled = True
            results.append(result)
        except RunCancelled:
            cancelled = True
            results.append(ModelResult(model_id, 'cancelled'))
        except Exception as error:
            if context.cancel_requested():
                cancelled = True
                results.append(ModelResult(model_id, 'cancelled'))
            else:
                context.error_sink(model_id, error)
                results.append(ModelResult(model_id, 'failed', errors=[ContractMessage(
                    'model_execution_failed', 'O modelo falhou; consulte os detalhes locais.',
                    {'exception_type': type(error).__name__})]))
        context.on_event({'study_id': plan.study_id, 'model_id': model_id,
                          'status': results[-1].status, 'step': step + 1,
                          'steps': len(plan.model_steps)})
    has_masks = any(result.masks for result in results)
    has_error = any(result.status in ('failed', 'interrupted', 'partial') for result in results)
    if cancelled or context.cancel_requested():
        status = 'cancelled'
    elif has_error:
        status = 'partial' if any(r.status in ('completed', 'empty', 'partial') for r in results) else 'failed'
    else:
        status = 'completed' if has_masks else 'empty'
    export_status = 'pending' if has_masks else ('empty' if status == 'empty' else 'failed')
    return StudyManifest(context.request_id, plan.study_id, context.plugin_version,
                         context.revision, context.reference, list(plan.selected_model_ids),
                         results, status, context.device_preference, context.effective_device,
                         export_status=export_status)

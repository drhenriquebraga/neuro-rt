"""Lightweight adapter boundary, safe to import outside scientific runtimes.

Paths are resolved by the trusted host before constructing this record. An
authorized input is a converted scalar 3D NIfTI, keyed by server-issued ticket.
Registrations map source LPS physical coordinates to the reference LPS frame;
they are trusted transform files, not instructions supplied by a web client.
The orchestrator owns process isolation and termination during native inference.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from ..study_types import InputBinding, ModelResult, SeriesDescriptor


class RunCancelled(RuntimeError):
    """Cooperative cancellation at an adapter boundary."""


@dataclass
class ModelRunContext:
    model_spec: dict
    bindings: list[InputBinding]
    reference: SeriesDescriptor
    series_index: dict[str, SeriesDescriptor]
    authorized_inputs: dict[str, Path]
    job_dir: Path
    models_dir: Path
    device: str
    cancel_requested: Callable[[], bool] = lambda: False
    progress: Callable[[str, float], None] = lambda stage, fraction: None
    source_to_reference: dict[str, Path] = field(default_factory=dict)
    allow_legacy_models: bool = True
    host_app: Path | None = None
    host_python: Path | None = None
    study_id: str = ''

    def checkpoint(self, stage: str, fraction: float):
        if self.cancel_requested():
            raise RunCancelled('Execução cancelada.')
        self.progress(stage, fraction)


@dataclass(frozen=True)
class PreparedInputs:
    channel_paths: list[str]
    channel_roles: list[str]
    working_geometry: dict
    reference: SeriesDescriptor
    transform_chain: list[dict]
    cache_key: str
    reference_path: str
    output_dir: str


@dataclass(frozen=True)
class GeometryReport:
    valid: bool
    expected_geometry: dict
    actual_geometry: dict
    errors: list[str]


class ModelAdapter(Protocol):
    def prepare(self, context: ModelRunContext) -> PreparedInputs: ...
    def predict(self, prepared: PreparedInputs, context: ModelRunContext): ...
    def normalize_result(self, raw, context: ModelRunContext) -> ModelResult: ...

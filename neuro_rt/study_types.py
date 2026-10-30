"""Lightweight NeuroRT boundary records; no runtime or image dependencies.

Constructors are records, not trust boundaries. Client requests and adapter
results must pass the validators in ``contracts`` before execution/persistence.
Tickets are opaque server-issued identifiers, never client filesystem paths.
"""
from dataclasses import asdict, dataclass, field
import json
from typing import Any, Literal, Union

ClassId = Union[str, int]
DevicePreference = Literal['auto', 'cpu', 'cuda']
ExecutionStatus = Literal['queued', 'preparing', 'running', 'restoring', 'exporting',
                          'visualizing', 'completed', 'partial', 'empty', 'failed',
                          'cancelled', 'interrupted']
ExportStatus = Literal['pending', 'completed', 'empty', 'failed', 'incomplete']
EXECUTION_STATUSES = frozenset(('queued', 'preparing', 'running', 'restoring',
                               'exporting', 'visualizing', 'completed', 'partial',
                               'empty', 'failed', 'cancelled', 'interrupted'))
EXPORT_STATUSES = frozenset(('pending', 'completed', 'empty', 'failed', 'incomplete'))


class ContractRecord:
    def to_dict(self) -> dict:
        """Return detached JSON data; reject NaN and non-JSON metadata."""
        return json.loads(json.dumps(asdict(self), allow_nan=False))


@dataclass(frozen=True)
class ContractMessage(ContractRecord):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SeriesDescriptor(ContractRecord):
    ticket: str
    series_uid: str
    subject_key: str
    study_key: str
    modality: str
    geometry: dict[str, Any] = field(default_factory=dict)
    sequence_candidates: list[dict[str, Any]] = field(default_factory=list)
    source_format: Literal['dicom', 'nifti'] = 'dicom'
    frame_of_reference_uid: str = ''
    sop_instance_uids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InputBinding(ContractRecord):
    role: str
    series_ticket: str
    certainty: Literal['certain', 'uncertain', 'unknown'] = 'unknown'
    association_source: Literal['manual', 'suggested', 'legacy'] = 'manual'
    warnings: list[ContractMessage] = field(default_factory=list)


@dataclass(frozen=True)
class StudyItem(ContractRecord):
    study_id: str
    reference: str
    model_ids: list[str]
    bindings_by_model: dict[str, list[InputBinding]]
    # Only the explicit v1 adapter populates this; v2 clients cannot supply paths.
    legacy_input_path: Union[str, None] = None


@dataclass(frozen=True)
class StudyRequest(ContractRecord):
    request_id: str
    explicit_request: bool
    studies: list[StudyItem]
    device: DevicePreference = 'auto'
    export_rtstruct: bool = False
    schema: str = 'neuro-rt/request/2'


@dataclass(frozen=True)
class MaskArtifact(ContractRecord):
    model_id: str
    class_id: ClassId
    path: str
    geometry: dict[str, Any] = field(default_factory=dict)
    space: str = 'reference'
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelResult(ContractRecord):
    model_id: str
    status: ExecutionStatus
    masks: list[MaskArtifact] = field(default_factory=list)
    geometry: dict[str, Any] = field(default_factory=dict)
    transformations: list[dict[str, Any]] = field(default_factory=list)
    versions: dict[str, str] = field(default_factory=dict)
    hashes: dict[str, str] = field(default_factory=dict)
    warnings: list[ContractMessage] = field(default_factory=list)
    errors: list[ContractMessage] = field(default_factory=list)


@dataclass(frozen=True)
class ExportReceipt(ContractRecord):
    published_file: str
    sop_instance_uid: str
    reference: str
    delivered_rois: list[str]
    omitted_rois: list[str]
    revision: int


@dataclass(frozen=True)
class StudyManifest(ContractRecord):
    request_id: str
    study_id: str
    plugin_version: str
    revision: int
    reference: SeriesDescriptor
    requested_model_ids: list[str]
    results: list[ModelResult]
    status: ExecutionStatus
    device_preference: DevicePreference
    effective_device: Literal['cpu', 'cuda']
    export_status: ExportStatus = 'pending'
    export_receipt: Union[ExportReceipt, None] = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    approval_status: str = 'UNAPPROVED'
    schema: str = 'neuro-rt/result/2'

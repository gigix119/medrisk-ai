"""Evaluation run read schemas (Phase 7).

`EvaluationRun.metrics`/`.calibration_metrics`/`.threshold_metrics`/`.confidence_intervals`
are stored as already-shaped JSON (see `app.research.domain.metric_shaping`) - these schemas
describe the read-side view of that JSON, not a re-derivation of it. No field here is ever
computed from a live model or live dataset rows; everything comes from what
`medrisk_research`'s ingestion CLI already persisted.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.research.domain.enums import ResultClassification, RunStatus


class EvaluationRunSummary(BaseModel):
    """Trimmed shape for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    study_id: uuid.UUID | None
    dataset_id: uuid.UUID | None
    model_id: str
    model_version: str
    split_name: str
    result_classification: ResultClassification
    status: RunStatus
    primary_metric_name: str | None
    primary_metric_value: float | None
    created_at: datetime
    completed_at: datetime | None


class EvaluationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_run_id: uuid.UUID | None
    study_id: uuid.UUID | None
    dataset_id: uuid.UUID | None
    model_deployment_id: uuid.UUID | None
    model_id: str
    model_version: str
    split_name: str
    result_classification: ResultClassification
    status: RunStatus
    protocol_hash: str | None
    primary_metric_name: str | None
    primary_metric_value: float | None
    metrics: dict | None
    confidence_intervals: dict | None
    calibration_metrics: dict | None
    threshold_metrics: dict | None
    artifact_manifest: dict | None
    notes: str | None
    created_at: datetime
    completed_at: datetime | None
    failure_reason: str | None


class MetricResult(BaseModel):
    name: str
    value: float | None
    status: str
    reason: str | None = None


class EvaluationMetricsRead(BaseModel):
    evaluation_id: uuid.UUID
    status: RunStatus
    scalar_metrics: list[MetricResult]
    counts: dict[str, int]
    confidence_intervals: dict | None = None


class ConfusionMatrixRead(BaseModel):
    """`available=False` (with `reason` set) when the run has no completed metrics yet, or
    its task type isn't one this phase derives a confusion matrix for - the master spec
    requires unavailable analysis to be reported explicitly, never hidden or fabricated."""

    evaluation_id: uuid.UUID
    available: bool
    reason: str | None = None
    class_labels: list[str] | None = None
    positive_class: str | None = None
    matrix: list[list[int]] | None = None
    normalized_matrix: list[list[float]] | None = None


class EvaluationSamplePredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_sample_id: uuid.UUID | None
    sample_key: str
    split: str
    ground_truth_label: str
    predicted_class: str
    probabilities: dict
    confidence: float | None
    is_correct: bool
    error_type: str | None
    inference_duration_ms: float | None


class CreateEvaluationRunRequest(BaseModel):
    study_id: uuid.UUID | None = None
    dataset_id: uuid.UUID
    model_id: str = Field(max_length=255)
    model_version: str = Field(max_length=50)
    split_name: str = Field(max_length=20)
    result_classification: ResultClassification

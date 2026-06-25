"""Experiment and evaluation run records (Phase 7).

`ExperimentRun` records one offline training/evaluation attempt from `medrisk_ml` (or the
ingestion of a pre-existing one) - reproducibility metadata only, no metrics of its own.
`EvaluationRun` is the record of one deterministic evaluation pass (one model, one dataset
version, one split). Per docs/PHASE_7_PROGRESS.md, a run with `status=COMPLETED` is treated as
immutable by every service in this codebase - re-evaluating creates a new row, nothing ever
edits a completed run's metrics/predictions in place. `EvaluationSamplePrediction` is one row
per evaluated sample; `dataset_sample_id` is nullable because not every evaluated sample can
necessarily be resolved back to a Phase 6 `DatasetSample` row (see the smoke-experiment
ingestion note in docs/PHASE_7_PROGRESS.md for a concrete, honest example of why).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.research.domain.enums import ResultClassification, RunStatus


class ExperimentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiment_runs"

    study_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_studies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        SAEnum(
            RunStatus,
            name="experiment_run_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=RunStatus.PENDING,
    )
    git_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    git_dirty: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    configuration_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dataset_manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_artifact_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hardware_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    software_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_artifact_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    def __repr__(self) -> str:
        return f"ExperimentRun(id={self.id!r}, run_name={self.run_name!r}, status={self.status!r})"


class EvaluationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_runs"

    experiment_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiment_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    study_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_studies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model_deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_deployments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    split_name: Mapped[str] = mapped_column(String(20), nullable=False)
    result_classification: Mapped[ResultClassification] = mapped_column(
        SAEnum(
            ResultClassification,
            name="evaluation_result_classification",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    status: Mapped[RunStatus] = mapped_column(
        SAEnum(
            RunStatus,
            name="evaluation_run_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=RunStatus.PENDING,
    )
    protocol_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    primary_metric_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    primary_metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence_intervals: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    calibration_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    threshold_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    artifact_manifest: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"EvaluationRun(id={self.id!r}, model_id={self.model_id!r}, "
            f"split_name={self.split_name!r}, status={self.status!r})"
        )


class EvaluationSamplePrediction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_sample_predictions"
    __table_args__ = (
        Index("ix_eval_sample_predictions_run_id_is_correct", "evaluation_run_id", "is_correct"),
    )

    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_sample_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dataset_samples.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sample_key: Mapped[str] = mapped_column(String(128), nullable=False)
    split: Mapped[str] = mapped_column(String(20), nullable=False)
    ground_truth_label: Mapped[str] = mapped_column(String(50), nullable=False)
    predicted_class: Mapped[str] = mapped_column(String(50), nullable=False)
    probabilities: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    inference_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return (
            f"EvaluationSamplePrediction(id={self.id!r}, "
            f"evaluation_run_id={self.evaluation_run_id!r}, sample_key={self.sample_key!r})"
        )

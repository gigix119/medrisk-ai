"""Prediction request/result records.

Phase 1 established the database schema with no real inference. Phase 3 wires up real
histopathology inference (see app/services/inference.py) and extends this model with audit
fields - never with raw image bytes, base64 explanations, or any patient-identifying data
(see docs/inference-security.md).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PredictionModule(str, enum.Enum):
    HISTOPATHOLOGY = "histopathology"
    SURVIVAL = "survival"


class PredictionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEW_REQUIRED = "review_required"


class Prediction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "predictions"
    __table_args__ = (Index("ix_predictions_user_id_created_at", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    module: Mapped[PredictionModule] = mapped_column(
        SAEnum(
            PredictionModule,
            name="prediction_module",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    status: Mapped[PredictionStatus] = mapped_column(
        SAEnum(
            PredictionStatus,
            name="prediction_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=PredictionStatus.PENDING,
    )
    input_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    inference_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- Phase 3: request/audit metadata ---
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- Phase 3: input technical metadata (never the raw image itself) ---
    input_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    input_filename_safe: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    input_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Phase 3: model identity (FK is nullable - history predates ModelDeployment rows) ---
    model_deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_deployments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_bundle_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- Phase 3: decision pipeline output ---
    raw_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibrated_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_class: Mapped[str | None] = mapped_column(String(50), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_lower_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_upper_bound: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Phase 3: timings ---
    preprocessing_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibration_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Phase 3: explanation + safe error reporting ---
    explanation_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    explanation_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    safe_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"Prediction(id={self.id!r}, user_id={self.user_id!r}, "
            f"module={self.module!r}, status={self.status!r})"
        )

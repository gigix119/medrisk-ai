"""Records the lifecycle of every model load attempt (Phase 3).

A model switch requires an application restart - there is no hot-swapping. Every load
attempt (successful or not) gets its own row, so the deployment history is a durable audit
trail of "what model was active when": rows are never deleted when a new model activates,
only superseded (`status` flips to INACTIVE, `deactivated_at` is stamped).
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.prediction import PredictionModule


class ModelDeploymentStatus(str, enum.Enum):
    LOADING = "loading"
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"


class ModelDeployment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per model-load attempt. Bundle filesystem paths are stored for internal
    administration only - never returned by any API response."""

    __tablename__ = "model_deployments"

    module: Mapped[PredictionModule] = mapped_column(
        SAEnum(
            PredictionModule,
            name="prediction_module",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    model_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    bundle_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    bundle_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    architecture: Mapped[str] = mapped_column(String(50), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dataset_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    synthetic_only: Mapped[bool] = mapped_column(Boolean, nullable=False)
    eligible_for_demo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    device: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[ModelDeploymentStatus] = mapped_column(
        SAEnum(
            ModelDeploymentStatus,
            name="model_deployment_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ModelDeploymentStatus.LOADING,
    )
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    warmup_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warmup_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return (
            f"ModelDeployment(id={self.id!r}, model_id={self.model_id!r}, "
            f"status={self.status!r})"
        )

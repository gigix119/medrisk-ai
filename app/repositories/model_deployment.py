"""Database access for ModelDeployment records (Phase 3 model-load audit trail)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_deployment import ModelDeployment, ModelDeploymentStatus
from app.models.prediction import PredictionModule


async def create(
    session: AsyncSession,
    *,
    module: PredictionModule,
    model_id: str,
    model_name: str,
    model_version: str,
    bundle_path: str,
    bundle_sha256: str,
    architecture: str,
    dataset_name: str,
    dataset_mode: str,
    synthetic_only: bool,
    eligible_for_demo: bool,
    device: str,
) -> ModelDeployment:
    deployment = ModelDeployment(
        module=module,
        model_id=model_id,
        model_name=model_name,
        model_version=model_version,
        bundle_path=bundle_path,
        bundle_sha256=bundle_sha256,
        architecture=architecture,
        dataset_name=dataset_name,
        dataset_mode=dataset_mode,
        synthetic_only=synthetic_only,
        eligible_for_demo=eligible_for_demo,
        device=device,
        status=ModelDeploymentStatus.LOADING,
    )
    session.add(deployment)
    await session.flush()
    return deployment


async def mark_active(
    session: AsyncSession,
    deployment: ModelDeployment,
    *,
    warmup_completed: bool,
    warmup_duration_ms: float | None,
) -> None:
    now = datetime.now(UTC)
    deployment.status = ModelDeploymentStatus.ACTIVE
    deployment.loaded_at = now
    deployment.activated_at = now
    deployment.warmup_completed = warmup_completed
    deployment.warmup_duration_ms = (
        int(warmup_duration_ms) if warmup_duration_ms is not None else None
    )
    await session.flush()


async def mark_failed(
    session: AsyncSession, deployment: ModelDeployment, *, failure_code: str
) -> None:
    deployment.status = ModelDeploymentStatus.FAILED
    deployment.failure_code = failure_code
    await session.flush()


async def deactivate_previous_active(
    session: AsyncSession, *, module: PredictionModule, exclude_id: uuid.UUID
) -> None:
    """Mark any other ACTIVE deployment for this module INACTIVE. Rows are never deleted."""
    await session.execute(
        update(ModelDeployment)
        .where(
            ModelDeployment.module == module,
            ModelDeployment.status == ModelDeploymentStatus.ACTIVE,
            ModelDeployment.id != exclude_id,
        )
        .values(status=ModelDeploymentStatus.INACTIVE, deactivated_at=datetime.now(UTC))
    )
    await session.flush()


async def get_active(session: AsyncSession, *, module: PredictionModule) -> ModelDeployment | None:
    result = await session.execute(
        select(ModelDeployment)
        .where(
            ModelDeployment.module == module, ModelDeployment.status == ModelDeploymentStatus.ACTIVE
        )
        .order_by(ModelDeployment.activated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()

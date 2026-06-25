"""Database access for `DatasetQualityAudit` / `DatasetLeakageAudit` records.

Both tables are append-only - there is deliberately no `update`/`upsert` here, only
`create_*` plus `get_latest_*`, mirroring how `ModelDeployment` rows are never edited after
creation (see app/models/model_deployment.py).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset_audit import DatasetLeakageAudit, DatasetQualityAudit
from app.research.domain.enums import AuditStatus


async def create_quality_audit(
    session: AsyncSession, *, dataset_id: uuid.UUID, status: AuditStatus, summary: dict
) -> DatasetQualityAudit:
    audit = DatasetQualityAudit(dataset_id=dataset_id, status=status, summary=summary)
    session.add(audit)
    await session.flush()
    return audit


async def get_latest_quality_audit(
    session: AsyncSession, dataset_id: uuid.UUID
) -> DatasetQualityAudit | None:
    result = await session.execute(
        select(DatasetQualityAudit)
        .where(DatasetQualityAudit.dataset_id == dataset_id)
        .order_by(DatasetQualityAudit.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_leakage_audit(
    session: AsyncSession, *, dataset_id: uuid.UUID, status: AuditStatus, summary: dict
) -> DatasetLeakageAudit:
    audit = DatasetLeakageAudit(dataset_id=dataset_id, status=status, summary=summary)
    session.add(audit)
    await session.flush()
    return audit


async def get_latest_leakage_audit(
    session: AsyncSession, dataset_id: uuid.UUID
) -> DatasetLeakageAudit | None:
    result = await session.execute(
        select(DatasetLeakageAudit)
        .where(DatasetLeakageAudit.dataset_id == dataset_id)
        .order_by(DatasetLeakageAudit.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()

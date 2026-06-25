"""Orchestrates dataset quality/leakage audits: resolves the dataset, runs the pure
computation in `dataset_quality_service`/`leakage_audit_service`, persists the result as a new
append-only audit row, and (for quality audits) computes/stores the dataset's manifest hash.

This is the one place that combines "compute" and "persist" for dataset audits, used
identically by the API (`POST /api/v1/research/datasets/{id}/quality-audit`) and by
`medrisk_research.cli` - so the two can never diverge in what counts as a passed audit.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.models.dataset import Dataset
from app.models.dataset_audit import DatasetLeakageAudit, DatasetQualityAudit
from app.models.dataset_sample import DatasetSample
from app.research.domain.hashing import config_hash
from app.research.repositories import dataset_audit as audit_repo
from app.research.services import dataset_quality_service, leakage_audit_service


async def _get_dataset_or_404(session: AsyncSession, dataset_id: uuid.UUID) -> Dataset:
    dataset = await session.get(Dataset, dataset_id)
    if dataset is None:
        raise ResourceNotFoundError("Dataset not found.")
    return dataset


async def _compute_manifest_hash(session: AsyncSession, dataset_id: uuid.UUID) -> str:
    result = await session.execute(
        select(
            DatasetSample.sample_key,
            DatasetSample.split,
            DatasetSample.ground_truth_label,
            DatasetSample.checksum_sha256,
        )
        .where(DatasetSample.dataset_id == dataset_id)
        .order_by(DatasetSample.sample_key)
    )
    rows = [list(row) for row in result.all()]
    return config_hash(rows)


async def run_and_persist_quality_audit(
    session: AsyncSession, *, dataset_id: uuid.UUID, datasets_root: Path
) -> DatasetQualityAudit:
    dataset = await _get_dataset_or_404(session, dataset_id)
    status, summary = await dataset_quality_service.run_quality_audit(
        session, dataset=dataset, datasets_root=datasets_root
    )
    dataset.manifest_hash = await _compute_manifest_hash(session, dataset_id)
    audit = await audit_repo.create_quality_audit(
        session, dataset_id=dataset_id, status=status, summary=summary
    )
    await session.commit()
    return audit


async def run_and_persist_leakage_audit(
    session: AsyncSession, *, dataset_id: uuid.UUID
) -> DatasetLeakageAudit:
    dataset = await _get_dataset_or_404(session, dataset_id)
    status, summary = await leakage_audit_service.run_leakage_audit(session, dataset=dataset)
    audit = await audit_repo.create_leakage_audit(
        session, dataset_id=dataset_id, status=status, summary=summary
    )
    await session.commit()
    return audit


async def get_latest_quality_audit(
    session: AsyncSession, dataset_id: uuid.UUID
) -> DatasetQualityAudit:
    await _get_dataset_or_404(session, dataset_id)
    audit = await audit_repo.get_latest_quality_audit(session, dataset_id)
    if audit is None:
        raise ResourceNotFoundError("No quality audit has been run for this dataset yet.")
    return audit


async def get_latest_leakage_audit(
    session: AsyncSession, dataset_id: uuid.UUID
) -> DatasetLeakageAudit:
    await _get_dataset_or_404(session, dataset_id)
    audit = await audit_repo.get_latest_leakage_audit(session, dataset_id)
    if audit is None:
        raise ResourceNotFoundError("No leakage audit has been run for this dataset yet.")
    return audit

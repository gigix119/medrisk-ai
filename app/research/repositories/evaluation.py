"""Database access for `ExperimentRun` / `EvaluationRun` / `EvaluationSamplePrediction`.

A completed `EvaluationRun` is treated as immutable by every caller in this codebase (see
docs/PHASE_7_PROGRESS.md) - there is no `update_completed_run` here on purpose. The only
mutations provided are: creating a pending run, marking it completed (once) or failed (once),
and appending its sample predictions. Re-evaluating means creating a brand new row.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation import EvaluationRun, EvaluationSamplePrediction, ExperimentRun
from app.research.domain.enums import ResultClassification, RunStatus


async def create_experiment_run(session: AsyncSession, **fields: object) -> ExperimentRun:
    run = ExperimentRun(**fields)
    session.add(run)
    await session.flush()
    return run


async def get_experiment_run(session: AsyncSession, run_id: uuid.UUID) -> ExperimentRun | None:
    return await session.get(ExperimentRun, run_id)


async def create_pending_evaluation_run(
    session: AsyncSession,
    *,
    dataset_id: uuid.UUID | None,
    model_id: str,
    model_version: str,
    split_name: str,
    result_classification: ResultClassification,
    study_id: uuid.UUID | None = None,
    experiment_run_id: uuid.UUID | None = None,
    model_deployment_id: uuid.UUID | None = None,
) -> EvaluationRun:
    run = EvaluationRun(
        dataset_id=dataset_id,
        model_id=model_id,
        model_version=model_version,
        split_name=split_name,
        result_classification=result_classification,
        study_id=study_id,
        experiment_run_id=experiment_run_id,
        model_deployment_id=model_deployment_id,
        status=RunStatus.PENDING,
    )
    session.add(run)
    await session.flush()
    return run


async def get_evaluation_run(session: AsyncSession, run_id: uuid.UUID) -> EvaluationRun | None:
    return await session.get(EvaluationRun, run_id)


async def list_evaluation_runs(
    session: AsyncSession,
    *,
    dataset_id: uuid.UUID | None = None,
    study_id: uuid.UUID | None = None,
    status: RunStatus | None = None,
    limit: int,
    offset: int,
) -> tuple[list[EvaluationRun], int]:
    base_query = select(EvaluationRun)
    if dataset_id is not None:
        base_query = base_query.where(EvaluationRun.dataset_id == dataset_id)
    if study_id is not None:
        base_query = base_query.where(EvaluationRun.study_id == study_id)
    if status is not None:
        base_query = base_query.where(EvaluationRun.status == status)

    total_result = await session.execute(select(func.count()).select_from(base_query.subquery()))
    total = total_result.scalar_one()

    items_result = await session.execute(
        base_query.order_by(EvaluationRun.created_at.desc()).limit(limit).offset(offset)
    )
    return list(items_result.scalars().all()), total


async def mark_evaluation_run_completed(
    session: AsyncSession,
    run: EvaluationRun,
    *,
    completed_at: datetime,
    primary_metric_name: str | None,
    primary_metric_value: float | None,
    metrics: dict,
    confidence_intervals: dict | None,
    calibration_metrics: dict | None,
    threshold_metrics: dict | None,
    artifact_manifest: dict | None,
    protocol_hash: str | None,
    notes: str | None,
) -> EvaluationRun:
    run.status = RunStatus.COMPLETED
    run.completed_at = completed_at
    run.primary_metric_name = primary_metric_name
    run.primary_metric_value = primary_metric_value
    run.metrics = metrics
    run.confidence_intervals = confidence_intervals
    run.calibration_metrics = calibration_metrics
    run.threshold_metrics = threshold_metrics
    run.artifact_manifest = artifact_manifest
    run.protocol_hash = protocol_hash
    run.notes = notes
    await session.flush()
    return run


async def mark_evaluation_run_failed(
    session: AsyncSession, run: EvaluationRun, *, failure_reason: str
) -> EvaluationRun:
    run.status = RunStatus.FAILED
    run.failure_reason = failure_reason
    await session.flush()
    return run


async def bulk_create_sample_predictions(
    session: AsyncSession, predictions: list[EvaluationSamplePrediction]
) -> None:
    session.add_all(predictions)
    await session.flush()


async def list_sample_predictions(
    session: AsyncSession,
    *,
    evaluation_run_id: uuid.UUID,
    is_correct: bool | None = None,
    ground_truth_label: str | None = None,
    predicted_class: str | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    limit: int,
    offset: int,
) -> tuple[list[EvaluationSamplePrediction], int]:
    base_query = select(EvaluationSamplePrediction).where(
        EvaluationSamplePrediction.evaluation_run_id == evaluation_run_id
    )
    if is_correct is not None:
        base_query = base_query.where(EvaluationSamplePrediction.is_correct == is_correct)
    if ground_truth_label is not None:
        base_query = base_query.where(
            EvaluationSamplePrediction.ground_truth_label == ground_truth_label
        )
    if predicted_class is not None:
        base_query = base_query.where(EvaluationSamplePrediction.predicted_class == predicted_class)
    if min_confidence is not None:
        base_query = base_query.where(EvaluationSamplePrediction.confidence >= min_confidence)
    if max_confidence is not None:
        base_query = base_query.where(EvaluationSamplePrediction.confidence <= max_confidence)

    total_result = await session.execute(select(func.count()).select_from(base_query.subquery()))
    total = total_result.scalar_one()

    items_result = await session.execute(
        base_query.order_by(EvaluationSamplePrediction.sample_key).limit(limit).offset(offset)
    )
    return list(items_result.scalars().all()), total

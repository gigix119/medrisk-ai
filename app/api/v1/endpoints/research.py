"""Research platform endpoints (Phase 7): studies, dataset quality/leakage audits, and
evaluation runs.

Every numeric result here was computed offline and persisted by `medrisk_research`'s
ingestion CLI (or, for dataset audits, computed inline - those checks are pure SQL/Python,
see `app.research.services.dataset_quality_service`/`leakage_audit_service`). The live API
process has no numpy/sklearn (see docs/PHASE_7_PROGRESS.md), so `POST .../evaluations` only
ever creates a `pending` row - actually running it is a CLI operation, mirroring how
`medrisk_ml.cli train/evaluate` already never run via API.
"""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.dependencies import CurrentUserDep, DbSessionDep, SettingsDep
from app.core.exceptions import ResourceNotFoundError
from app.repositories import dataset as dataset_repo
from app.research.domain.enums import RunStatus
from app.research.repositories import study as study_repo
from app.research.schemas.audit import DatasetLeakageAuditRead, DatasetQualityAuditRead
from app.research.schemas.evaluation import (
    ConfusionMatrixRead,
    CreateEvaluationRunRequest,
    EvaluationMetricsRead,
    EvaluationRunRead,
    EvaluationRunSummary,
    EvaluationSamplePredictionRead,
    MetricResult,
)
from app.research.schemas.study import StudyRead, StudyValidationResult
from app.research.services import dataset_audit_service, evaluation_service, study_service
from app.research.services.evaluation_service import build_confusion_matrix
from app.schemas.common import Page

router = APIRouter()


# --- Studies -----------------------------------------------------------------------------


@router.get("/studies", response_model=Page[StudyRead], summary="List research studies")
async def list_studies(
    current_user: CurrentUserDep,
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[StudyRead]:
    items, total = await study_repo.list_studies(session, limit=limit, offset=offset)
    return Page[StudyRead](
        items=[StudyRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/studies/{study_id}", response_model=StudyRead, summary="Get one research study")
async def get_study(
    study_id: uuid.UUID, current_user: CurrentUserDep, session: DbSessionDep
) -> StudyRead:
    study = await study_repo.get_by_id(session, study_id)
    if study is None:
        raise ResourceNotFoundError("Research study not found.")
    return StudyRead.model_validate(study)


@router.post(
    "/studies/{study_id}/validate",
    response_model=StudyValidationResult,
    summary="Re-validate a study's stored configuration against the current schema",
)
async def validate_study(
    study_id: uuid.UUID, current_user: CurrentUserDep, session: DbSessionDep
) -> StudyValidationResult:
    study = await study_repo.get_by_id(session, study_id)
    if study is None:
        raise ResourceNotFoundError("Research study not found.")
    config, errors = study_service.validate_config(study.configuration)
    if config is None:
        return StudyValidationResult(valid=False, errors=errors)
    return StudyValidationResult(valid=True, configuration_hash=study.configuration_hash)


# --- Dataset quality / leakage audits -----------------------------------------------------


@router.get(
    "/datasets/{dataset_id}/quality",
    response_model=DatasetQualityAuditRead,
    summary="Get the most recent dataset quality audit",
)
async def get_dataset_quality(
    dataset_id: uuid.UUID, current_user: CurrentUserDep, session: DbSessionDep
) -> DatasetQualityAuditRead:
    audit = await dataset_audit_service.get_latest_quality_audit(session, dataset_id)
    return DatasetQualityAuditRead.model_validate(audit)


@router.post(
    "/datasets/{dataset_id}/quality-audit",
    response_model=DatasetQualityAuditRead,
    status_code=status.HTTP_201_CREATED,
    summary="Run a new dataset quality audit",
)
async def run_dataset_quality_audit(
    dataset_id: uuid.UUID,
    current_user: CurrentUserDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> DatasetQualityAuditRead:
    audit = await dataset_audit_service.run_and_persist_quality_audit(
        session, dataset_id=dataset_id, datasets_root=Path(settings.DATASETS_ROOT)
    )
    return DatasetQualityAuditRead.model_validate(audit)


@router.get(
    "/datasets/{dataset_id}/leakage",
    response_model=DatasetLeakageAuditRead,
    summary="Get the most recent dataset leakage audit",
)
async def get_dataset_leakage(
    dataset_id: uuid.UUID, current_user: CurrentUserDep, session: DbSessionDep
) -> DatasetLeakageAuditRead:
    audit = await dataset_audit_service.get_latest_leakage_audit(session, dataset_id)
    return DatasetLeakageAuditRead.model_validate(audit)


@router.post(
    "/datasets/{dataset_id}/leakage-audit",
    response_model=DatasetLeakageAuditRead,
    status_code=status.HTTP_201_CREATED,
    summary="Run a new dataset leakage audit",
)
async def run_dataset_leakage_audit(
    dataset_id: uuid.UUID, current_user: CurrentUserDep, session: DbSessionDep
) -> DatasetLeakageAuditRead:
    audit = await dataset_audit_service.run_and_persist_leakage_audit(
        session, dataset_id=dataset_id
    )
    return DatasetLeakageAuditRead.model_validate(audit)


# --- Evaluations ----------------------------------------------------------------------------


@router.get(
    "/evaluations", response_model=Page[EvaluationRunSummary], summary="List evaluation runs"
)
async def list_evaluations(
    current_user: CurrentUserDep,
    session: DbSessionDep,
    dataset_id: uuid.UUID | None = None,
    study_id: uuid.UUID | None = None,
    eval_status: Annotated[RunStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EvaluationRunSummary]:
    items, total = await evaluation_service.list_evaluations(
        session,
        dataset_id=dataset_id,
        study_id=study_id,
        status=eval_status,
        limit=limit,
        offset=offset,
    )
    return Page[EvaluationRunSummary](
        items=[EvaluationRunSummary.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/evaluations",
    response_model=EvaluationRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a pending evaluation run",
)
async def create_evaluation(
    payload: CreateEvaluationRunRequest, current_user: CurrentUserDep, session: DbSessionDep
) -> EvaluationRunRead:
    dataset = await dataset_repo.get_by_id(session, payload.dataset_id)
    if dataset is None:
        raise ResourceNotFoundError("Dataset not found.")
    run = await evaluation_service.create_pending_evaluation(
        session,
        dataset_id=payload.dataset_id,
        model_id=payload.model_id,
        model_version=payload.model_version,
        split_name=payload.split_name,
        result_classification=payload.result_classification,
        study_id=payload.study_id,
    )
    await session.commit()
    return EvaluationRunRead.model_validate(run)


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=EvaluationRunRead,
    summary="Get one evaluation run",
)
async def get_evaluation(
    evaluation_id: uuid.UUID, current_user: CurrentUserDep, session: DbSessionDep
) -> EvaluationRunRead:
    run = await evaluation_service.get_evaluation_detail(session, evaluation_id)
    return EvaluationRunRead.model_validate(run)


@router.get(
    "/evaluations/{evaluation_id}/metrics",
    response_model=EvaluationMetricsRead,
    summary="Get one evaluation run's metrics",
)
async def get_evaluation_metrics(
    evaluation_id: uuid.UUID, current_user: CurrentUserDep, session: DbSessionDep
) -> EvaluationMetricsRead:
    run = await evaluation_service.get_evaluation_detail(session, evaluation_id)
    metrics = run.metrics or {}
    scalar_metrics = [MetricResult(**entry) for entry in metrics.get("scalar_metrics", [])]
    return EvaluationMetricsRead(
        evaluation_id=run.id,
        status=run.status,
        scalar_metrics=scalar_metrics,
        counts=metrics.get("counts", {}),
        confidence_intervals=run.confidence_intervals,
    )


@router.get(
    "/evaluations/{evaluation_id}/confusion-matrix",
    response_model=ConfusionMatrixRead,
    summary="Get one evaluation run's confusion matrix",
)
async def get_evaluation_confusion_matrix(
    evaluation_id: uuid.UUID, current_user: CurrentUserDep, session: DbSessionDep
) -> ConfusionMatrixRead:
    run = await evaluation_service.get_evaluation_detail(session, evaluation_id)
    return build_confusion_matrix(run)


@router.get(
    "/evaluations/{evaluation_id}/errors",
    response_model=Page[EvaluationSamplePredictionRead],
    summary="List per-sample predictions for one evaluation run (error analysis)",
)
async def list_evaluation_errors(
    evaluation_id: uuid.UUID,
    current_user: CurrentUserDep,
    session: DbSessionDep,
    is_correct: bool | None = None,
    ground_truth_label: str | None = None,
    predicted_class: str | None = None,
    min_confidence: Annotated[float | None, Query(ge=0.0, le=1.0)] = None,
    max_confidence: Annotated[float | None, Query(ge=0.0, le=1.0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EvaluationSamplePredictionRead]:
    items, total = await evaluation_service.list_sample_predictions(
        session,
        evaluation_run_id=evaluation_id,
        is_correct=is_correct,
        ground_truth_label=ground_truth_label,
        predicted_class=predicted_class,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        limit=limit,
        offset=offset,
    )
    return Page[EvaluationSamplePredictionRead](
        items=[EvaluationSamplePredictionRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )

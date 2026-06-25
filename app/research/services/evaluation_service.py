"""Read-oriented evaluation-run service (Phase 7).

Every numeric value served here was already computed offline by `medrisk_research`'s
ingestion CLI and persisted as JSON on `EvaluationRun` - this module never recomputes a
metric, it only resolves rows, enforces 404s, and reshapes already-stored JSON into the
API's response schemas (e.g. building a confusion matrix from stored TP/TN/FP/FN counts is
arithmetic, not a re-evaluation).
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.models.evaluation import EvaluationRun, EvaluationSamplePrediction
from app.research.domain.enums import ResultClassification, RunStatus
from app.research.repositories import evaluation as evaluation_repo
from app.research.schemas.evaluation import ConfusionMatrixRead


async def get_evaluation_detail(session: AsyncSession, evaluation_id: uuid.UUID) -> EvaluationRun:
    run = await evaluation_repo.get_evaluation_run(session, evaluation_id)
    if run is None:
        raise ResourceNotFoundError("Evaluation run not found.")
    return run


async def list_evaluations(
    session: AsyncSession,
    *,
    dataset_id: uuid.UUID | None,
    study_id: uuid.UUID | None,
    status: RunStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[EvaluationRun], int]:
    return await evaluation_repo.list_evaluation_runs(
        session,
        dataset_id=dataset_id,
        study_id=study_id,
        status=status,
        limit=limit,
        offset=offset,
    )


async def create_pending_evaluation(
    session: AsyncSession,
    *,
    dataset_id: uuid.UUID,
    model_id: str,
    model_version: str,
    split_name: str,
    result_classification: ResultClassification,
    study_id: uuid.UUID | None,
) -> EvaluationRun:
    """Creates a `pending` row only. The live API process has no numpy/sklearn (see
    docs/PHASE_7_PROGRESS.md "Architecture decisions", item 2) and therefore cannot itself run
    the evaluation - actually populating this run's metrics requires
    `python -m medrisk_research.cli evaluate --evaluation-id <id>` in the offline ml
    environment, mirroring how `medrisk_ml.cli train/evaluate` already never run via API."""
    return await evaluation_repo.create_pending_evaluation_run(
        session,
        dataset_id=dataset_id,
        model_id=model_id,
        model_version=model_version,
        split_name=split_name,
        result_classification=result_classification,
        study_id=study_id,
    )


_UNAVAILABLE_CONFUSION_MATRIX_REASON = (
    "No completed binary-classification metrics are available for this evaluation run yet."
)


def build_confusion_matrix(run: EvaluationRun) -> ConfusionMatrixRead:
    """Derives a confusion matrix from the binary TP/TN/FP/FN counts already stored on
    `run.metrics` - `available=False` (never a fabricated matrix) when the run has no metrics
    yet or the counts needed aren't present (e.g. a non-binary task this phase doesn't model)."""
    metrics = run.metrics or {}
    counts = metrics.get("counts") or {}
    class_names = metrics.get("class_names")
    tn, fp = counts.get("true_negative"), counts.get("false_positive")
    fn, tp = counts.get("false_negative"), counts.get("true_positive")
    if (
        not class_names
        or len(class_names) != 2
        or tn is None
        or fp is None
        or fn is None
        or tp is None
    ):
        return ConfusionMatrixRead(
            evaluation_id=run.id, available=False, reason=_UNAVAILABLE_CONFUSION_MATRIX_REASON
        )
    tn, fp, fn, tp = int(tn), int(fp), int(fn), int(tp)

    negative, positive = class_names[0], class_names[1]
    matrix = [[tn, fp], [fn, tp]]
    normalized: list[list[float]] = []
    for row in matrix:
        row_total = sum(row)
        normalized.append([value / row_total if row_total else 0.0 for value in row])

    return ConfusionMatrixRead(
        evaluation_id=run.id,
        available=True,
        class_labels=[negative, positive],
        positive_class=metrics.get("positive_class", positive),
        matrix=matrix,
        normalized_matrix=normalized,
    )


async def list_sample_predictions(
    session: AsyncSession,
    *,
    evaluation_run_id: uuid.UUID,
    is_correct: bool | None,
    ground_truth_label: str | None,
    predicted_class: str | None,
    min_confidence: float | None,
    max_confidence: float | None,
    limit: int,
    offset: int,
) -> tuple[list[EvaluationSamplePrediction], int]:
    await get_evaluation_detail(session, evaluation_run_id)  # 404s before touching predictions
    return await evaluation_repo.list_sample_predictions(
        session,
        evaluation_run_id=evaluation_run_id,
        is_correct=is_correct,
        ground_truth_label=ground_truth_label,
        predicted_class=predicted_class,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        limit=limit,
        offset=offset,
    )

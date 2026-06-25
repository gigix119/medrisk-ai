"""Database access for Prediction records."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prediction import Prediction, PredictionModule, PredictionStatus


async def create_pending(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    module: PredictionModule,
    request_id: str | None,
    client_reference: str | None,
    dataset_id: uuid.UUID | None = None,
    dataset_sample_id: uuid.UUID | None = None,
) -> Prediction:
    prediction = Prediction(
        user_id=user_id,
        module=module,
        status=PredictionStatus.PENDING,
        request_id=request_id,
        client_reference=client_reference,
        dataset_id=dataset_id,
        dataset_sample_id=dataset_sample_id,
    )
    session.add(prediction)
    await session.flush()
    return prediction


async def mark_completed(
    session: AsyncSession,
    prediction: Prediction,
    *,
    status: PredictionStatus,
    input_metadata: dict[str, object],
    result: dict[str, object],
    model_deployment_id: uuid.UUID,
    model_id: str,
    model_name: str,
    model_version: str,
    model_bundle_sha256: str,
    input_sha256: str,
    input_filename_safe: str | None,
    input_mime_type: str | None,
    input_format: str,
    input_size_bytes: int,
    input_width: int,
    input_height: int,
    processed_width: int,
    processed_height: int,
    raw_probability: float,
    calibrated_probability: float,
    confidence_score: float,
    predicted_class: str,
    decision: str,
    threshold: float,
    review_lower_bound: float | None,
    review_upper_bound: float | None,
    preprocessing_time_ms: float,
    inference_time_ms: int,
    calibration_time_ms: float,
    explanation_time_ms: float | None,
    total_time_ms: float,
    explanation_requested: bool,
    explanation_status: str,
    split: str | None = None,
    ground_truth_label: str | None = None,
    is_correct: bool | None = None,
) -> None:
    prediction.status = status
    prediction.input_metadata = input_metadata
    prediction.result = result
    prediction.model_deployment_id = model_deployment_id
    prediction.model_id = model_id
    prediction.model_name = model_name
    prediction.model_version = model_version
    prediction.model_bundle_sha256 = model_bundle_sha256
    prediction.input_sha256 = input_sha256
    prediction.input_filename_safe = input_filename_safe
    prediction.input_mime_type = input_mime_type
    prediction.input_format = input_format
    prediction.input_size_bytes = input_size_bytes
    prediction.input_width = input_width
    prediction.input_height = input_height
    prediction.processed_width = processed_width
    prediction.processed_height = processed_height
    prediction.raw_probability = raw_probability
    prediction.calibrated_probability = calibrated_probability
    prediction.confidence_score = confidence_score
    prediction.predicted_class = predicted_class
    prediction.decision = decision
    prediction.threshold = threshold
    prediction.review_lower_bound = review_lower_bound
    prediction.review_upper_bound = review_upper_bound
    prediction.preprocessing_time_ms = preprocessing_time_ms
    prediction.inference_time_ms = inference_time_ms
    prediction.calibration_time_ms = calibration_time_ms
    prediction.explanation_time_ms = explanation_time_ms
    prediction.total_time_ms = total_time_ms
    prediction.explanation_requested = explanation_requested
    prediction.explanation_status = explanation_status
    prediction.split = split
    prediction.ground_truth_label = ground_truth_label
    prediction.is_correct = is_correct
    prediction.completed_at = datetime.now(UTC)
    await session.flush()


async def mark_failed(
    session: AsyncSession,
    prediction: Prediction,
    *,
    error_code: str,
    safe_error_message: str,
) -> None:
    prediction.status = PredictionStatus.FAILED
    prediction.error_code = error_code
    prediction.safe_error_message = safe_error_message
    prediction.completed_at = datetime.now(UTC)
    await session.flush()


async def get_by_id_for_user(
    session: AsyncSession, *, prediction_id: uuid.UUID, user_id: uuid.UUID
) -> Prediction | None:
    result = await session.execute(
        select(Prediction).where(Prediction.id == prediction_id, Prediction.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_for_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    limit: int,
    offset: int,
    module: PredictionModule | None = None,
    status: PredictionStatus | None = None,
    decision: str | None = None,
    model_version: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    dataset_id: uuid.UUID | None = None,
    split: str | None = None,
    predicted_class: str | None = None,
    is_correct: bool | None = None,
) -> tuple[list[Prediction], int]:
    """Return one page of a user's predictions (newest first, id as a stable tie-breaker),
    plus the total count matching the same filters."""
    base_query = select(Prediction).where(Prediction.user_id == user_id)
    if module is not None:
        base_query = base_query.where(Prediction.module == module)
    if status is not None:
        base_query = base_query.where(Prediction.status == status)
    if decision is not None:
        base_query = base_query.where(Prediction.decision == decision)
    if model_version is not None:
        base_query = base_query.where(Prediction.model_version == model_version)
    if created_from is not None:
        base_query = base_query.where(Prediction.created_at >= created_from)
    if created_to is not None:
        base_query = base_query.where(Prediction.created_at <= created_to)
    if dataset_id is not None:
        base_query = base_query.where(Prediction.dataset_id == dataset_id)
    if split is not None:
        base_query = base_query.where(Prediction.split == split)
    if predicted_class is not None:
        base_query = base_query.where(Prediction.predicted_class == predicted_class)
    if is_correct is not None:
        base_query = base_query.where(Prediction.is_correct == is_correct)

    total_result = await session.execute(select(func.count()).select_from(base_query.subquery()))
    total = total_result.scalar_one()

    items_result = await session.execute(
        base_query.order_by(desc(Prediction.created_at), desc(Prediction.id))
        .limit(limit)
        .offset(offset)
    )
    items = list(items_result.scalars().all())
    return items, total

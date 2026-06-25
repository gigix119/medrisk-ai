"""Dataset registry + controlled ("research") inference on a known dataset sample.

`run_sample_prediction` reuses the exact same `medrisk_inference.service.validate_upload` /
`run_validated_inference` calls that `app.services.prediction.run_histopathology_prediction`
already uses for arbitrary uploads - the only difference is where the image bytes come from
(the dataset registry's own filesystem, resolved exclusively server-side, never from a
client-supplied path) and that the resulting `Prediction` row also records dataset/sample
provenance and a computed `is_correct` flag.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AppError, ResourceNotFoundError
from app.models.dataset import Dataset
from app.models.dataset_sample import DatasetSample
from app.models.prediction import Prediction, PredictionModule, PredictionStatus
from app.repositories import dataset as dataset_repo
from app.repositories import prediction as prediction_repo
from app.services.model_deployment import ActiveHistopathologyModel
from app.services.prediction import (
    GENERIC_SERVER_MESSAGE,
    predict_with_concurrency_limit,
    translate_inference_error,
)
from medrisk_inference.exceptions import InferenceError
from medrisk_inference.service import validate_upload
from medrisk_inference.types import InferenceResult

logger = logging.getLogger(__name__)


async def list_datasets(
    session: AsyncSession, *, limit: int, offset: int
) -> tuple[list[Dataset], int]:
    return await dataset_repo.list_active_public(session, limit=limit, offset=offset)


async def get_dataset_detail(session: AsyncSession, dataset_id: uuid.UUID) -> Dataset:
    dataset = await dataset_repo.get_by_id(session, dataset_id)
    if dataset is None or not dataset.is_active or not dataset.is_public:
        raise ResourceNotFoundError("Dataset not found.")
    return dataset


async def list_dataset_samples(
    session: AsyncSession,
    *,
    dataset_id: uuid.UUID,
    split: str | None,
    class_index: int | None,
    limit: int,
    offset: int,
) -> tuple[list[DatasetSample], int]:
    await get_dataset_detail(session, dataset_id)  # 404s before touching samples at all
    return await dataset_repo.list_samples(
        session,
        dataset_id=dataset_id,
        split=split,
        class_index=class_index,
        limit=limit,
        offset=offset,
    )


async def get_dataset_sample_detail(
    session: AsyncSession, *, dataset_id: uuid.UUID, sample_id: uuid.UUID
) -> tuple[Dataset, DatasetSample]:
    dataset = await get_dataset_detail(session, dataset_id)
    sample = await dataset_repo.get_sample_by_id(
        session, dataset_id=dataset_id, sample_id=sample_id
    )
    if sample is None:
        raise ResourceNotFoundError("Dataset sample not found.")
    return dataset, sample


def resolve_sample_image_path(
    dataset: Dataset, sample: DatasetSample, *, datasets_root: Path
) -> Path:
    """Resolve `sample.relative_path` to an absolute path, never trusting it to stay inside
    the dataset's own image root - mirrors `medrisk_inference.bundle._ensure_no_symlink_escape`.
    Neither `dataset.slug`/`dataset.version` nor `sample.relative_path` are ever taken from a
    request; both come from rows already looked up by validated UUIDs."""
    dataset_root = (datasets_root / dataset.slug / dataset.version).resolve()
    candidate = (dataset_root / sample.relative_path).resolve()
    if not candidate.is_relative_to(dataset_root):
        raise ResourceNotFoundError("Dataset sample image not found.")
    if not candidate.is_file():
        raise ResourceNotFoundError("Dataset sample image not found.")
    return candidate


async def run_sample_prediction(
    session: AsyncSession,
    *,
    settings: Settings,
    active_model: ActiveHistopathologyModel,
    semaphore: asyncio.Semaphore,
    user_id: uuid.UUID,
    request_id: str | None,
    dataset_id: uuid.UUID,
    sample_id: uuid.UUID,
    include_explanation: bool,
    client_reference: str | None,
) -> tuple[Prediction, InferenceResult, Dataset, DatasetSample]:
    dataset, sample = await get_dataset_sample_detail(
        session, dataset_id=dataset_id, sample_id=sample_id
    )
    image_path = resolve_sample_image_path(
        dataset, sample, datasets_root=Path(settings.DATASETS_ROOT)
    )
    image_bytes = image_path.read_bytes()

    try:
        validated_image, validation_ms = validate_upload(
            active_model.runtime, image_bytes, declared_content_type=sample.mime_type
        )
    except InferenceError as exc:
        raise translate_inference_error(exc) from exc

    prediction = await prediction_repo.create_pending(
        session,
        user_id=user_id,
        module=PredictionModule.HISTOPATHOLOGY,
        request_id=request_id,
        client_reference=client_reference,
        dataset_id=dataset.id,
        dataset_sample_id=sample.id,
    )
    await session.commit()

    try:
        result = await predict_with_concurrency_limit(
            settings=settings,
            runtime=active_model.runtime,
            semaphore=semaphore,
            validated_image=validated_image,
            validation_ms=validation_ms,
            include_explanation=include_explanation,
        )
    except AppError as exc:
        await prediction_repo.mark_failed(
            session, prediction, error_code=exc.error_code, safe_error_message=exc.message
        )
        await session.commit()
        logger.warning(
            "Dataset-sample inference failed: request_id=%s prediction_id=%s code=%s",
            request_id,
            prediction.id,
            exc.error_code,
        )
        raise
    except Exception:
        await prediction_repo.mark_failed(
            session,
            prediction,
            error_code="INFERENCE_FAILED",
            safe_error_message=GENERIC_SERVER_MESSAGE,
        )
        await session.commit()
        logger.exception(
            "Unexpected error during dataset-sample inference: request_id=%s prediction_id=%s",
            request_id,
            prediction.id,
        )
        raise AppError(
            GENERIC_SERVER_MESSAGE, error_code="INFERENCE_FAILED", status_code=500
        ) from None

    is_correct = result.decision.predicted_class == sample.ground_truth_label
    final_status = (
        PredictionStatus.REVIEW_REQUIRED
        if result.decision.decision == "review_required"
        else PredictionStatus.COMPLETED
    )
    review_policy = result.decision.review_policy
    await prediction_repo.mark_completed(
        session,
        prediction,
        status=final_status,
        input_metadata={"declared_content_type": sample.mime_type, "source": "dataset_sample"},
        result={
            "class_names": list(result.model.class_names),
            "positive_class": result.model.positive_class,
            "architecture": result.model.architecture,
        },
        model_deployment_id=active_model.deployment_id,
        model_id=result.model.model_id,
        model_name=result.model.model_name,
        model_version=result.model.model_version,
        model_bundle_sha256=result.model.bundle_sha256,
        input_sha256=result.validated_image.sha256,
        input_filename_safe=sample.filename,
        input_mime_type=sample.mime_type,
        input_format=result.validated_image.declared_format,
        input_size_bytes=result.validated_image.size_bytes,
        input_width=result.validated_image.width,
        input_height=result.validated_image.height,
        processed_width=result.processed.processed_width,
        processed_height=result.processed.processed_height,
        raw_probability=result.raw_output.raw_probability,
        calibrated_probability=result.decision.calibrated_probability,
        confidence_score=result.decision.confidence_score,
        predicted_class=result.decision.predicted_class,
        decision=result.decision.decision,
        threshold=result.decision.threshold,
        review_lower_bound=review_policy.negative_probability_max if review_policy else None,
        review_upper_bound=review_policy.positive_probability_min if review_policy else None,
        preprocessing_time_ms=result.timings.preprocessing_ms,
        inference_time_ms=round(result.timings.inference_ms),
        calibration_time_ms=result.timings.calibration_ms,
        explanation_time_ms=result.timings.explanation_ms,
        total_time_ms=result.timings.total_ms,
        explanation_requested=include_explanation,
        explanation_status=result.explanation.status,
        split=sample.split,
        ground_truth_label=sample.ground_truth_label,
        is_correct=is_correct,
    )
    await session.commit()
    return prediction, result, dataset, sample

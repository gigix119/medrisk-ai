"""Prediction orchestration.

Histopathology inference (Phase 3) follows a strict transaction boundary: a `pending` row
is created and committed *before* the model runs, the actual inference happens with no open
transaction, and the row is updated to its final state in a second commit. This way an
expensive (and potentially slow/hanging) model forward pass never holds a database
transaction open. See docs/inference-architecture.md "Database transaction flow".
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import (
    AppError,
    InferenceQueueFullError,
    InferenceTimeoutError,
    ResourceNotFoundError,
)
from app.models.prediction import Prediction, PredictionModule, PredictionStatus
from app.repositories import prediction as prediction_repo
from app.services.model_deployment import ActiveHistopathologyModel
from medrisk_inference.exceptions import InferenceError, UploadEmptyError, UploadTooLargeError
from medrisk_inference.runtime import HistopathologyModelRuntime
from medrisk_inference.service import run_validated_inference, validate_upload
from medrisk_inference.types import InferenceResult, ValidatedImage
from medrisk_inference.utils import sanitize_filename

logger = logging.getLogger(__name__)

_UPLOAD_CHUNK_BYTES = 64 * 1024

# Maps medrisk_inference error codes to HTTP statuses. Codes not listed default to 500.
# 5xx codes get a generic client-facing message (the underlying message may describe
# internal model/runtime state); 4xx codes are already client-safe (they only ever describe
# the upload itself) and are shown verbatim.
_STATUS_BY_ERROR_CODE: dict[str, int] = {
    "MODEL_BUNDLE_INVALID": 503,
    "MODEL_VERSION_INCOMPATIBLE": 503,
    "MODEL_NOT_READY": 503,
    "MODEL_WARMUP_FAILED": 503,
    "UPLOAD_EMPTY": 400,
    "UPLOAD_TOO_LARGE": 413,
    "UNSUPPORTED_IMAGE_FORMAT": 415,
    "IMAGE_DECODE_FAILED": 422,
    "IMAGE_DIMENSIONS_INVALID": 422,
    "IMAGE_PIXEL_LIMIT_EXCEEDED": 422,
    "IMAGE_MULTIFRAME_NOT_SUPPORTED": 422,
    "IMAGE_MIME_MISMATCH": 422,
    "MODEL_OUTPUT_INVALID": 500,
    "CALIBRATION_FAILED": 500,
    "DECISION_POLICY_INVALID": 500,
    "EXPLANATION_NOT_SUPPORTED": 422,
    "EXPLANATION_FAILED": 500,
    "INFERENCE_FAILED": 500,
}
GENERIC_SERVER_MESSAGE = "The inference request could not be completed due to an internal error."


def translate_inference_error(exc: InferenceError) -> AppError:
    status_code = _STATUS_BY_ERROR_CODE.get(exc.error_code, 500)
    message = exc.message if status_code < 500 else GENERIC_SERVER_MESSAGE
    return AppError(message, error_code=exc.error_code, status_code=status_code)


async def read_upload_within_limit(file: UploadFile, *, max_bytes: int) -> bytes:
    """Stream the upload in chunks, enforcing `max_bytes` against the actual byte count -
    never trusting `Content-Length` (which a client can misreport) or `UploadFile.read()`
    with no limit (which would let an attacker exhaust memory).
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise translate_inference_error(
                UploadTooLargeError(f"Upload exceeds the {max_bytes}-byte limit.")
            )
        chunks.append(chunk)

    data = b"".join(chunks)
    if not data:
        raise translate_inference_error(UploadEmptyError("Uploaded file is empty."))
    return data


async def validate_histopathology_upload(
    runtime: HistopathologyModelRuntime,
    image_bytes: bytes,
    *,
    declared_content_type: str | None,
) -> tuple[ValidatedImage, float]:
    """Validation runs *before* any Prediction row is created - an invalid upload never
    produces an audit row at all."""
    try:
        return validate_upload(runtime, image_bytes, declared_content_type=declared_content_type)
    except InferenceError as exc:
        raise translate_inference_error(exc) from exc


async def run_histopathology_prediction(
    session: AsyncSession,
    *,
    settings: Settings,
    active_model: ActiveHistopathologyModel,
    semaphore: asyncio.Semaphore,
    user_id: uuid.UUID,
    request_id: str | None,
    validated_image: ValidatedImage,
    validation_ms: float,
    include_explanation: bool,
    client_reference: str | None,
    original_filename: str | None,
    declared_content_type: str | None,
) -> tuple[Prediction, InferenceResult]:
    prediction = await prediction_repo.create_pending(
        session,
        user_id=user_id,
        module=PredictionModule.HISTOPATHOLOGY,
        request_id=request_id,
        client_reference=client_reference,
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
            "Histopathology inference failed: request_id=%s prediction_id=%s code=%s",
            request_id,
            prediction.id,
            exc.error_code,
        )
        raise
    except Exception:
        # Anything not already a recognized AppError/InferenceError is a genuine bug, not an
        # expected failure mode - still must mark the row failed (never leave it stuck in
        # `pending` forever) and never persist or return the raw exception.
        await prediction_repo.mark_failed(
            session,
            prediction,
            error_code="INFERENCE_FAILED",
            safe_error_message=GENERIC_SERVER_MESSAGE,
        )
        await session.commit()
        logger.exception(
            "Unexpected error during histopathology inference: request_id=%s prediction_id=%s",
            request_id,
            prediction.id,
        )
        raise AppError(
            GENERIC_SERVER_MESSAGE, error_code="INFERENCE_FAILED", status_code=500
        ) from None

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
        input_metadata={"declared_content_type": declared_content_type},
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
        input_filename_safe=sanitize_filename(original_filename),
        input_mime_type=declared_content_type,
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
    )
    await session.commit()
    return prediction, result


async def predict_with_concurrency_limit(
    *,
    settings: Settings,
    runtime: HistopathologyModelRuntime,
    semaphore: asyncio.Semaphore,
    validated_image: ValidatedImage,
    validation_ms: float,
    include_explanation: bool,
) -> InferenceResult:
    try:
        await asyncio.wait_for(
            semaphore.acquire(), timeout=settings.INFERENCE_QUEUE_TIMEOUT_SECONDS
        )
    except TimeoutError as exc:
        raise InferenceQueueFullError(
            retry_after_seconds=max(1, round(settings.INFERENCE_QUEUE_TIMEOUT_SECONDS))
        ) from exc

    try:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    run_validated_inference,
                    runtime,
                    validated_image,
                    validation_ms=validation_ms,
                    include_explanation=include_explanation,
                ),
                timeout=settings.INFERENCE_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            raise InferenceTimeoutError() from exc
        except InferenceError as exc:
            raise translate_inference_error(exc) from exc
    finally:
        semaphore.release()


async def get_prediction_detail(
    session: AsyncSession, *, user_id: uuid.UUID, prediction_id: uuid.UUID
) -> Prediction:
    """Returns 404 (never 403) for a prediction that exists but belongs to another user, so
    this endpoint can't be used to probe for the existence of other users' records."""
    prediction = await prediction_repo.get_by_id_for_user(
        session, prediction_id=prediction_id, user_id=user_id
    )
    if prediction is None:
        raise ResourceNotFoundError("Prediction not found.")
    return prediction


async def get_history(
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
    return await prediction_repo.list_for_user(
        session,
        user_id=user_id,
        limit=limit,
        offset=offset,
        module=module,
        status=status,
        decision=decision,
        model_version=model_version,
        created_from=created_from,
        created_to=created_to,
        dataset_id=dataset_id,
        split=split,
        predicted_class=predicted_class,
        is_correct=is_correct,
    )

"""Prediction endpoints.

`/histopathology` performs real inference against the active model bundle (Phase 3).
`/survival` remains an honest placeholder: Phase 3 ships no survival model, so it returns
HTTP 501 rather than any score. History and detail reads only ever return records owned by
the caller.
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.dependencies import (
    ActiveHistopathologyModelDep,
    CurrentUserDep,
    DbSessionDep,
    InferenceSemaphoreDep,
    SettingsDep,
)
from app.core.logging import get_request_id
from app.core.rate_limit import InferenceRateLimitDep
from app.models.prediction import PredictionModule, PredictionStatus
from app.schemas.common import Page
from app.schemas.prediction import (
    ExplanationSchema,
    HistopathologyPredictionResponse,
    InputInfoSchema,
    ModelInfoSchema,
    PredictionNotAvailableResponse,
    PredictionRead,
    PredictionRequest,
    ReviewPolicySchema,
    TimingsSchema,
)
from app.services import prediction as prediction_service

router = APIRouter()

_NOT_IMPLEMENTED_MESSAGE = (
    "The Phase 1 API foundation is operational, but no {module} model is loaded yet. "
    "Real inference will be implemented in a later phase. "
    "This endpoint must not be used for medical decisions."
)


@router.post(
    "/histopathology",
    response_model=HistopathologyPredictionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Histopathology image classification",
)
async def predict_histopathology(
    current_user: CurrentUserDep,
    session: DbSessionDep,
    settings: SettingsDep,
    active_model: ActiveHistopathologyModelDep,
    semaphore: InferenceSemaphoreDep,
    _rate_limit: InferenceRateLimitDep,
    file: Annotated[UploadFile, File(description="A PNG or JPEG histopathology patch.")],
    include_explanation: Annotated[bool, Form()] = False,
    client_reference: Annotated[
        str | None,
        Form(
            max_length=100,
            description="Optional non-sensitive client-side reference. Must not contain "
            "patient-identifying information.",
        ),
    ] = None,
) -> HistopathologyPredictionResponse:
    image_bytes = await prediction_service.read_upload_within_limit(
        file, max_bytes=settings.MAX_UPLOAD_BYTES
    )
    validated_image, validation_ms = await prediction_service.validate_histopathology_upload(
        active_model.runtime, image_bytes, declared_content_type=file.content_type
    )
    prediction, result = await prediction_service.run_histopathology_prediction(
        session,
        settings=settings,
        active_model=active_model,
        semaphore=semaphore,
        user_id=current_user.id,
        request_id=get_request_id(),
        validated_image=validated_image,
        validation_ms=validation_ms,
        include_explanation=include_explanation,
        client_reference=client_reference,
        original_filename=file.filename,
        declared_content_type=file.content_type,
    )

    decision = result.decision
    review_policy = decision.review_policy
    return HistopathologyPredictionResponse(
        prediction_id=prediction.id,
        status=prediction.status,
        decision=decision.decision,
        predicted_class=decision.predicted_class,
        raw_probability=result.raw_output.raw_probability,
        calibrated_probability=decision.calibrated_probability,
        predicted_class_probability=decision.predicted_class_probability,
        confidence_score=decision.confidence_score,
        positive_class=result.model.positive_class,
        threshold=decision.threshold,
        review_policy=(
            ReviewPolicySchema(
                negative_probability_max=review_policy.negative_probability_max,
                positive_probability_min=review_policy.positive_probability_min,
            )
            if review_policy
            else None
        ),
        input=InputInfoSchema(
            sha256=result.validated_image.sha256,
            format=result.validated_image.declared_format,
            mime_type=file.content_type,
            size_bytes=result.validated_image.size_bytes,
            original_width=result.validated_image.width,
            original_height=result.validated_image.height,
            processed_width=result.processed.processed_width,
            processed_height=result.processed.processed_height,
        ),
        model=ModelInfoSchema(
            model_id=result.model.model_id,
            model_name=result.model.model_name,
            version=result.model.model_version,
            architecture=result.model.architecture,
            synthetic_only=result.model.synthetic_only,
            eligible_for_demo=result.model.eligible_for_demo,
        ),
        timings=TimingsSchema(
            validation_ms=result.timings.validation_ms,
            preprocessing_ms=result.timings.preprocessing_ms,
            inference_ms=result.timings.inference_ms,
            calibration_ms=result.timings.calibration_ms,
            explanation_ms=result.timings.explanation_ms,
            total_ms=result.timings.total_ms,
        ),
        explanation=ExplanationSchema(
            status=result.explanation.status,
            method=result.explanation.method,
            target_layer=result.explanation.target_layer,
            mime_type=result.explanation.mime_type,
            encoding=result.explanation.encoding,
            data=result.explanation.data,
            width=result.explanation.width,
            height=result.explanation.height,
            generation_time_ms=result.explanation.generation_time_ms,
            error_code=result.explanation.error_code,
            disclaimer=result.explanation.disclaimer,
        ),
        created_at=prediction.created_at,
    )


@router.post(
    "/survival",
    response_model=PredictionNotAvailableResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="[Placeholder] Survival analysis",
)
async def predict_survival(
    payload: PredictionRequest, current_user: CurrentUserDep
) -> PredictionNotAvailableResponse:
    return PredictionNotAvailableResponse(
        module=PredictionModule.SURVIVAL,
        message=_NOT_IMPLEMENTED_MESSAGE.format(module="survival"),
    )


@router.get(
    "/history",
    response_model=Page[PredictionRead],
    summary="List the current user's predictions",
)
async def get_history(
    current_user: CurrentUserDep,
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    module: PredictionModule | None = None,
    status_filter: Annotated[PredictionStatus | None, Query(alias="status")] = None,
    decision: Annotated[str | None, Query(max_length=20)] = None,
    model_version: Annotated[str | None, Query(max_length=50)] = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    dataset_id: uuid.UUID | None = None,
    split: Annotated[str | None, Query(max_length=20)] = None,
    predicted_class: Annotated[str | None, Query(max_length=50)] = None,
    is_correct: bool | None = None,
) -> Page[PredictionRead]:
    items, total = await prediction_service.get_history(
        session,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        module=module,
        status=status_filter,
        decision=decision,
        model_version=model_version,
        created_from=created_from,
        created_to=created_to,
        dataset_id=dataset_id,
        split=split,
        predicted_class=predicted_class,
        is_correct=is_correct,
    )
    return Page[PredictionRead](
        items=[PredictionRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{prediction_id}",
    response_model=PredictionRead,
    summary="Get one of the current user's predictions by id",
)
async def get_prediction(
    prediction_id: uuid.UUID, current_user: CurrentUserDep, session: DbSessionDep
) -> PredictionRead:
    prediction = await prediction_service.get_prediction_detail(
        session, user_id=current_user.id, prediction_id=prediction_id
    )
    return PredictionRead.model_validate(prediction)

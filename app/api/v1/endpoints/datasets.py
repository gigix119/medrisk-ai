"""Dataset registry + controlled ("research") inference endpoints (Phase 6).

Every route resolves `dataset_id`/`sample_id` against the registry first - no path, filename,
or other filesystem detail is ever accepted from a request. See
`app.services.dataset.resolve_sample_image_path` for the path-traversal defense applied
before any file is read.
"""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import FileResponse

from app.api.dependencies import (
    ActiveHistopathologyModelDep,
    CurrentUserDep,
    DbSessionDep,
    InferenceSemaphoreDep,
    SettingsDep,
)
from app.core.logging import get_request_id
from app.schemas.common import Page
from app.schemas.dataset import (
    DatasetRead,
    DatasetSampleRead,
    PredictOnSampleRequest,
    PredictOnSampleResponse,
)
from app.schemas.prediction import (
    ExplanationSchema,
    InputInfoSchema,
    ModelInfoSchema,
    ReviewPolicySchema,
    TimingsSchema,
)
from app.services import dataset as dataset_service

router = APIRouter()


def _sample_image_url(dataset_id: uuid.UUID, sample_id: uuid.UUID) -> str:
    return f"/api/v1/datasets/{dataset_id}/samples/{sample_id}/image"


@router.get("", response_model=Page[DatasetRead], summary="List available research datasets")
async def list_datasets(
    current_user: CurrentUserDep,
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[DatasetRead]:
    items, total = await dataset_service.list_datasets(session, limit=limit, offset=offset)
    return Page[DatasetRead](
        items=[DatasetRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{dataset_id}", response_model=DatasetRead, summary="Get one dataset's metadata")
async def get_dataset(
    dataset_id: uuid.UUID, current_user: CurrentUserDep, session: DbSessionDep
) -> DatasetRead:
    dataset = await dataset_service.get_dataset_detail(session, dataset_id)
    return DatasetRead.model_validate(dataset)


@router.get(
    "/{dataset_id}/samples",
    response_model=Page[DatasetSampleRead],
    summary="List a dataset's research samples",
)
async def list_dataset_samples(
    dataset_id: uuid.UUID,
    current_user: CurrentUserDep,
    session: DbSessionDep,
    split: str | None = None,
    class_index: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[DatasetSampleRead]:
    items, total = await dataset_service.list_dataset_samples(
        session,
        dataset_id=dataset_id,
        split=split,
        class_index=class_index,
        limit=limit,
        offset=offset,
    )
    return Page[DatasetSampleRead](
        items=[
            DatasetSampleRead.model_validate(
                {**item.__dict__, "image_url": _sample_image_url(dataset_id, item.id)}
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{dataset_id}/samples/{sample_id}",
    response_model=DatasetSampleRead,
    summary="Get one research sample's metadata",
)
async def get_dataset_sample(
    dataset_id: uuid.UUID,
    sample_id: uuid.UUID,
    current_user: CurrentUserDep,
    session: DbSessionDep,
) -> DatasetSampleRead:
    _dataset, sample = await dataset_service.get_dataset_sample_detail(
        session, dataset_id=dataset_id, sample_id=sample_id
    )
    return DatasetSampleRead.model_validate(
        {**sample.__dict__, "image_url": _sample_image_url(dataset_id, sample_id)}
    )


@router.get(
    "/{dataset_id}/samples/{sample_id}/image",
    summary="Fetch a research sample's image bytes",
    responses={200: {"content": {"image/png": {}}}},
)
async def get_dataset_sample_image(
    dataset_id: uuid.UUID,
    sample_id: uuid.UUID,
    current_user: CurrentUserDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> FileResponse:
    dataset, sample = await dataset_service.get_dataset_sample_detail(
        session, dataset_id=dataset_id, sample_id=sample_id
    )
    image_path = dataset_service.resolve_sample_image_path(
        dataset, sample, datasets_root=Path(settings.DATASETS_ROOT)
    )
    return FileResponse(image_path, media_type=sample.mime_type)


@router.post(
    "/{dataset_id}/samples/{sample_id}/predict",
    response_model=PredictOnSampleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run research inference on a known dataset sample",
)
async def predict_on_sample(
    dataset_id: uuid.UUID,
    sample_id: uuid.UUID,
    payload: PredictOnSampleRequest,
    current_user: CurrentUserDep,
    session: DbSessionDep,
    settings: SettingsDep,
    active_model: ActiveHistopathologyModelDep,
    semaphore: InferenceSemaphoreDep,
) -> PredictOnSampleResponse:
    prediction, result, dataset, sample = await dataset_service.run_sample_prediction(
        session,
        settings=settings,
        active_model=active_model,
        semaphore=semaphore,
        user_id=current_user.id,
        request_id=get_request_id(),
        dataset_id=dataset_id,
        sample_id=sample_id,
        include_explanation=payload.include_explanation,
        client_reference=payload.client_reference,
    )

    decision = result.decision
    review_policy = decision.review_policy
    warnings: list[str] = []
    if dataset.is_synthetic:
        warnings.append(
            "This dataset is synthetic and demonstrative - it does not represent real "
            "tissue and must not be treated as medical evidence."
        )

    return PredictOnSampleResponse(
        prediction_id=prediction.id,
        dataset_id=dataset.id,
        dataset_sample_id=sample.id,
        dataset_name=dataset.name,
        dataset_slug=dataset.slug,
        dataset_version=dataset.version,
        sample_key=sample.sample_key,
        split=sample.split,
        ground_truth_label=sample.ground_truth_label,
        predicted_class=decision.predicted_class,
        is_correct=decision.predicted_class == sample.ground_truth_label,
        decision=decision.decision,
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
            mime_type=sample.mime_type,
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
        warnings=warnings,
    )

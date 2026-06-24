"""Prediction endpoints.

The two inference endpoints are honest placeholders: Phase 1 ships no
trained model, so they return HTTP 501 instead of any classification or
score. History reads real (currently always-empty) rows owned by the caller.
"""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.dependencies import CurrentUserDep, DbSessionDep
from app.models.prediction import PredictionModule
from app.schemas.common import Page
from app.schemas.prediction import PredictionNotAvailableResponse, PredictionRead, PredictionRequest
from app.services import prediction as prediction_service

router = APIRouter()

_NOT_IMPLEMENTED_MESSAGE = (
    "The Phase 1 API foundation is operational, but no {module} model is loaded yet. "
    "Real inference will be implemented in a later phase. "
    "This endpoint must not be used for medical decisions."
)


@router.post(
    "/histopathology",
    response_model=PredictionNotAvailableResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="[Placeholder] Histopathology image classification",
)
async def predict_histopathology(
    payload: PredictionRequest, current_user: CurrentUserDep
) -> PredictionNotAvailableResponse:
    return PredictionNotAvailableResponse(
        module=PredictionModule.HISTOPATHOLOGY,
        message=_NOT_IMPLEMENTED_MESSAGE.format(module="histopathology"),
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
) -> Page[PredictionRead]:
    items, total = await prediction_service.get_history(
        session, user_id=current_user.id, limit=limit, offset=offset
    )
    return Page[PredictionRead](
        items=[PredictionRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )

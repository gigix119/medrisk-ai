"""Prediction orchestration.

Phase 1 ships no real ML model. Creating a prediction is intentionally not
implemented here - see app/api/v1/endpoints/predictions.py, which returns an
honest HTTP 501 without calling into this module. Only history reading is
implemented.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prediction import Prediction
from app.repositories import prediction as prediction_repo


async def get_history(
    session: AsyncSession, *, user_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[Prediction], int]:
    return await prediction_repo.list_for_user(session, user_id=user_id, limit=limit, offset=offset)

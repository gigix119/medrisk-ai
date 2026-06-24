"""Database access for Prediction records."""

import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prediction import Prediction


async def list_for_user(
    session: AsyncSession, *, user_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[Prediction], int]:
    """Return one page of a user's predictions (newest first), plus the total count."""
    base_query = select(Prediction).where(Prediction.user_id == user_id)

    total_result = await session.execute(select(func.count()).select_from(base_query.subquery()))
    total = total_result.scalar_one()

    items_result = await session.execute(
        base_query.order_by(desc(Prediction.created_at)).limit(limit).offset(offset)
    )
    items = list(items_result.scalars().all())
    return items, total

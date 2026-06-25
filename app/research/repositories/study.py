"""Database access for `ResearchStudy` records."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.research_study import ResearchStudy


async def get_by_id(session: AsyncSession, study_id: uuid.UUID) -> ResearchStudy | None:
    return await session.get(ResearchStudy, study_id)


async def get_by_slug(session: AsyncSession, slug: str) -> ResearchStudy | None:
    result = await session.execute(select(ResearchStudy).where(ResearchStudy.slug == slug))
    return result.scalar_one_or_none()


async def list_studies(
    session: AsyncSession, *, limit: int, offset: int
) -> tuple[list[ResearchStudy], int]:
    base_query = select(ResearchStudy)
    total_result = await session.execute(select(func.count()).select_from(base_query.subquery()))
    total = total_result.scalar_one()

    items_result = await session.execute(
        base_query.order_by(ResearchStudy.created_at.desc()).limit(limit).offset(offset)
    )
    return list(items_result.scalars().all()), total


async def upsert_study(session: AsyncSession, *, slug: str, **fields: object) -> ResearchStudy:
    """Insert a new study row, or update an existing one (matched by slug) in place - used by
    the `medrisk_research` CLI's study-loading command, never by request-serving code."""
    study = await get_by_slug(session, slug)
    if study is None:
        study = ResearchStudy(slug=slug, **fields)
        session.add(study)
    else:
        for key, value in fields.items():
            setattr(study, key, value)
    await session.flush()
    return study

"""Database access for Dataset / DatasetSample records."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset
from app.models.dataset_sample import DatasetSample


async def list_active_public(
    session: AsyncSession, *, limit: int, offset: int
) -> tuple[list[Dataset], int]:
    base_query = select(Dataset).where(Dataset.is_active == True, Dataset.is_public == True)  # noqa: E712
    total_result = await session.execute(select(func.count()).select_from(base_query.subquery()))
    total = total_result.scalar_one()

    items_result = await session.execute(
        base_query.order_by(Dataset.name).limit(limit).offset(offset)
    )
    return list(items_result.scalars().all()), total


async def get_by_id(session: AsyncSession, dataset_id: uuid.UUID) -> Dataset | None:
    return await session.get(Dataset, dataset_id)


async def get_by_slug(session: AsyncSession, slug: str) -> Dataset | None:
    result = await session.execute(select(Dataset).where(Dataset.slug == slug))
    return result.scalar_one_or_none()


async def list_samples(
    session: AsyncSession,
    *,
    dataset_id: uuid.UUID,
    split: str | None = None,
    class_index: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[DatasetSample], int]:
    base_query = select(DatasetSample).where(DatasetSample.dataset_id == dataset_id)
    if split is not None:
        base_query = base_query.where(DatasetSample.split == split)
    if class_index is not None:
        base_query = base_query.where(DatasetSample.class_index == class_index)

    total_result = await session.execute(select(func.count()).select_from(base_query.subquery()))
    total = total_result.scalar_one()

    items_result = await session.execute(
        base_query.order_by(DatasetSample.sample_key).limit(limit).offset(offset)
    )
    return list(items_result.scalars().all()), total


async def get_sample_by_id(
    session: AsyncSession, *, dataset_id: uuid.UUID, sample_id: uuid.UUID
) -> DatasetSample | None:
    """Always scoped by both ids together, so a sample from dataset A can never be returned
    through a URL naming dataset B."""
    result = await session.execute(
        select(DatasetSample).where(
            DatasetSample.id == sample_id, DatasetSample.dataset_id == dataset_id
        )
    )
    return result.scalar_one_or_none()


async def get_sample_by_key(
    session: AsyncSession, *, dataset_id: uuid.UUID, sample_key: str
) -> DatasetSample | None:
    result = await session.execute(
        select(DatasetSample).where(
            DatasetSample.dataset_id == dataset_id, DatasetSample.sample_key == sample_key
        )
    )
    return result.scalar_one_or_none()


async def upsert_dataset(session: AsyncSession, *, slug: str, **fields: object) -> Dataset:
    """Insert a new dataset row, or update an existing one (matched by slug) in place -
    used only by the dev seed script, never by request-serving code."""
    dataset = await get_by_slug(session, slug)
    if dataset is None:
        dataset = Dataset(slug=slug, **fields)
        session.add(dataset)
    else:
        for key, value in fields.items():
            setattr(dataset, key, value)
    await session.flush()
    return dataset


async def upsert_sample(
    session: AsyncSession, *, dataset_id: uuid.UUID, sample_key: str, **fields: object
) -> DatasetSample:
    sample = await get_sample_by_key(session, dataset_id=dataset_id, sample_key=sample_key)
    if sample is None:
        sample = DatasetSample(dataset_id=dataset_id, sample_key=sample_key, **fields)
        session.add(sample)
    else:
        for key, value in fields.items():
            setattr(sample, key, value)
    await session.flush()
    return sample

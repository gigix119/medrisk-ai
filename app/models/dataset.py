"""Dataset registry (Phase 6).

A `Dataset` describes one curated, browsable collection of research samples (today: only the
in-repo synthetic demonstration dataset). It is metadata only - the actual image bytes live on
disk under `Settings.DATASETS_ROOT/<slug>/<version>/`, addressed exclusively through
`DatasetSample.relative_path`, which is never returned by any API response (same principle as
`ModelDeployment.bundle_path`).
"""

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Dataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("slug", name="uq_datasets_slug"),)

    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    license_name: Mapped[str] = mapped_column(String(255), nullable=False)
    license_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    intended_use: Mapped[str] = mapped_column(Text, nullable=False)
    prohibited_use: Mapped[str] = mapped_column(Text, nullable=False)
    modality: Mapped[str] = mapped_column(String(50), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    classes: Mapped[list] = mapped_column(JSONB, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_width: Mapped[int] = mapped_column(Integer, nullable=False)
    image_height: Mapped[int] = mapped_column(Integer, nullable=False)
    image_channels: Mapped[int] = mapped_column(Integer, nullable=False)
    split_names: Mapped[list] = mapped_column(JSONB, nullable=False)
    class_distribution: Mapped[dict] = mapped_column(JSONB, nullable=False)
    preprocessing_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    known_limitations: Mapped[str] = mapped_column(Text, nullable=False)
    ethical_notes: Mapped[str] = mapped_column(Text, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # --- Phase 7: manifest immutability (nullable - computed lazily by the dataset quality
    # audit service, not at seed time, so existing rows don't need a backfill migration) ---
    manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return f"Dataset(id={self.id!r}, slug={self.slug!r}, version={self.version!r})"

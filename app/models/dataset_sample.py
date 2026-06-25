"""Dataset sample manifest rows (Phase 6).

Each row describes one research sample belonging to a `Dataset`. `relative_path` is resolved
to an absolute filesystem path exclusively server-side (see
`app.services.dataset.resolve_sample_image_path`) and is never included in any API response -
clients only ever see a `sample_id` + dataset_id and fetch the image through the dedicated
image endpoint.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DatasetSample(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dataset_samples"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id", "sample_key", name="uq_dataset_samples_dataset_id_sample_key"
        ),
        Index("ix_dataset_samples_dataset_id_split", "dataset_id", "split"),
        Index("ix_dataset_samples_dataset_id_class_index", "dataset_id", "class_index"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sample_key: Mapped[str] = mapped_column(String(128), nullable=False)
    split: Mapped[str] = mapped_column(String(20), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    ground_truth_label: Mapped[str] = mapped_column(String(50), nullable=False)
    class_index: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    license_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"DatasetSample(id={self.id!r}, dataset_id={self.dataset_id!r}, "
            f"sample_key={self.sample_key!r})"
        )

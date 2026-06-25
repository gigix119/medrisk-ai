"""Dataset quality and leakage audit records (Phase 7).

Each row is one point-in-time audit run against a `Dataset` version. Audits are append-only -
re-running an audit creates a new row rather than overwriting the previous one, so a dataset's
audit history is never lost (mirrors `ModelDeployment`'s append-only lifecycle rows). The two
tables use the same `AuditStatus` Python enum but distinct native Postgres enum types
(`dataset_quality_audit_status` / `dataset_leakage_audit_status`), to avoid the two columns
fighting over ownership of one shared native type.
"""

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.research.domain.enums import AuditStatus


class DatasetQualityAudit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dataset_quality_audits"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[AuditStatus] = mapped_column(
        SAEnum(
            AuditStatus,
            name="dataset_quality_audit_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False)

    def __repr__(self) -> str:
        return (
            f"DatasetQualityAudit(id={self.id!r}, dataset_id={self.dataset_id!r}, "
            f"status={self.status!r})"
        )


class DatasetLeakageAudit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dataset_leakage_audits"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[AuditStatus] = mapped_column(
        SAEnum(
            AuditStatus,
            name="dataset_leakage_audit_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False)

    def __repr__(self) -> str:
        return (
            f"DatasetLeakageAudit(id={self.id!r}, dataset_id={self.dataset_id!r}, "
            f"status={self.status!r})"
        )

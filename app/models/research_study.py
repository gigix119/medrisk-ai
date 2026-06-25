"""Research study specification + record (Phase 7).

A `ResearchStudy` is the persisted, hashable record of a formal study configuration (see
`app.research.schemas.study.StudyConfig`): title, research question, hypothesis, which
dataset/version it targets, and its current scientific-maturity classification. The full
validated configuration is stored as JSONB (`configuration`) alongside a stable SHA-256 hash
of its canonical JSON form (`configuration_hash`), so two studies can be compared for exact
configuration equality without re-parsing YAML. `dataset_version` is a snapshot string,
deliberately independent of `dataset_id`'s live FK target - `Dataset` rows (Phase 6) are
edited in place rather than versioned as new rows, so a study pins the version it was
actually validated against even if the referenced dataset is later updated.
"""

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.research.domain.enums import ScientificMaturity, StudyStatus


class ResearchStudy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_studies"

    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    research_question: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[StudyStatus] = mapped_column(
        SAEnum(
            StudyStatus,
            name="research_study_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=StudyStatus.DRAFT,
    )
    scientific_maturity: Mapped[ScientificMaturity] = mapped_column(
        SAEnum(
            ScientificMaturity,
            name="scientific_maturity",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ScientificMaturity.UNKNOWN,
    )
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    dataset_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    configuration: Mapped[dict] = mapped_column(JSONB, nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"ResearchStudy(id={self.id!r}, slug={self.slug!r}, status={self.status!r})"

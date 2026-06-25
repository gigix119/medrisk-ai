"""Study-configuration validation and persistence (Phase 7).

Operates on an already-parsed `StudyConfig` (or raw dict) - never on YAML text. YAML is a
file-authoring convenience handled exclusively by `medrisk_research.cli`, which has PyYAML
available in its offline ml/CLI environment; the live API only ever receives/returns JSON,
and both the API and CLI defer to this module so the two can never validate differently.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.research_study import ResearchStudy
from app.research.domain.enums import StudyStatus
from app.research.domain.hashing import config_hash
from app.research.repositories import study as study_repo
from app.research.schemas.study import StudyConfig


def validate_config(raw_config: dict[str, Any]) -> tuple[StudyConfig | None, list[str]]:
    """Validates a raw (already-YAML/JSON-parsed) dict against `StudyConfig`. Returns
    `(None, errors)` on failure - never partially constructs a config from invalid input."""
    try:
        return StudyConfig.model_validate(raw_config), []
    except ValidationError as exc:
        return None, [str(error) for error in exc.errors()]


async def upsert_study_from_config(
    session: AsyncSession, config: StudyConfig, *, dataset_id: uuid.UUID | None
) -> ResearchStudy:
    configuration = config.model_dump(mode="json")
    return await study_repo.upsert_study(
        session,
        slug=config.slug,
        title=config.title,
        research_question=config.research_question,
        hypothesis=config.hypothesis,
        status=StudyStatus.VALIDATED,
        scientific_maturity=config.governance.scientific_maturity,
        dataset_id=dataset_id,
        dataset_version=config.dataset.dataset_version,
        configuration=configuration,
        configuration_hash=config_hash(configuration),
    )

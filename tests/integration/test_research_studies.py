"""Integration tests for research-study endpoints (Phase 7).

Builds a `ResearchStudy` via `app.research.services.study_service` (the exact path
`medrisk_research.cli load-study` uses), pointed at the `seeded_dataset` fixture, then
exercises the read/validate endpoints.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.research.services import study_service
from tests.integration.conftest import AuthTokens, SeededDataset


def _valid_config(dataset_slug: str, dataset_version: str) -> dict[str, object]:
    return {
        "slug": "integration-test-study",
        "title": "Integration test study",
        "research_question": "Does the study persistence path work end to end?",
        "dataset": {
            "dataset_slug": dataset_slug,
            "dataset_version": dataset_version,
            "task_type": "binary_classification",
            "target_classes": ["negative", "positive"],
            "positive_class": "positive",
        },
        "preprocessing": {
            "input_width": 32,
            "input_height": 32,
            "normalization_strategy": "per_dataset_mean_std",
        },
        "training": {
            "architecture": "baseline_cnn",
            "loss_function": "binary_cross_entropy",
            "optimizer": "adamw",
            "learning_rate": 0.001,
            "batch_size": 16,
            "epochs": 2,
            "checkpoint_selection_metric": "roc_auc",
        },
        "evaluation": {"evaluation_split": "test", "primary_metric": "roc_auc"},
        "governance": {
            "intended_use": "Testing.",
            "out_of_scope_use": "Not for real use.",
            "known_limitations": "Test fixture.",
            "scientific_maturity": "synthetic_demo",
        },
    }


async def _create_study(db_session: AsyncSession, seeded_dataset: SeededDataset) -> uuid.UUID:
    from app.models.dataset import Dataset

    dataset = await db_session.get(Dataset, seeded_dataset.dataset_id)
    assert dataset is not None
    config, errors = study_service.validate_config(_valid_config(dataset.slug, dataset.version))
    assert config is not None, errors
    study = await study_service.upsert_study_from_config(db_session, config, dataset_id=dataset.id)
    await db_session.commit()
    return study.id


async def test_list_studies_includes_created_study(
    client: AsyncClient,
    auth_tokens: AuthTokens,
    db_session: AsyncSession,
    seeded_dataset: SeededDataset,
) -> None:
    study_id = await _create_study(db_session, seeded_dataset)
    response = await client.get("/api/v1/research/studies", headers=auth_tokens.auth_header)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert str(study_id) in ids


async def test_get_study_detail(
    client: AsyncClient,
    auth_tokens: AuthTokens,
    db_session: AsyncSession,
    seeded_dataset: SeededDataset,
) -> None:
    study_id = await _create_study(db_session, seeded_dataset)
    response = await client.get(
        f"/api/v1/research/studies/{study_id}", headers=auth_tokens.auth_header
    )
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "integration-test-study"
    assert body["scientific_maturity"] == "synthetic_demo"
    assert body["status"] == "validated"


async def test_validate_study_returns_valid_for_current_schema(
    client: AsyncClient,
    auth_tokens: AuthTokens,
    db_session: AsyncSession,
    seeded_dataset: SeededDataset,
) -> None:
    study_id = await _create_study(db_session, seeded_dataset)
    response = await client.post(
        f"/api/v1/research/studies/{study_id}/validate", headers=auth_tokens.auth_header
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["configuration_hash"] is not None


async def test_get_unknown_study_returns_404(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    response = await client.get(
        f"/api/v1/research/studies/{uuid.uuid4()}", headers=auth_tokens.auth_header
    )
    assert response.status_code == 404

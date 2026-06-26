"""Authorization tests for the research write endpoints (Phase 8).

Any authenticated user could previously trigger a dataset audit or create an evaluation run
(see docs/PHASE_8_PROGRESS.md "Real gaps found"). These three endpoints are now gated by
`CurrentSuperuserDep` (app/api/dependencies.py); a regular authenticated user must get 403,
never 201/200, and never a partial side effect.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.integration.conftest import AuthTokens, SeededDataset


async def test_regular_user_cannot_run_quality_audit(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    response = await client.post(
        f"/api/v1/research/datasets/{seeded_dataset.dataset_id}/quality-audit",
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "AUTHORIZATION_FAILED"


async def test_regular_user_cannot_run_leakage_audit(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    response = await client.post(
        f"/api/v1/research/datasets/{seeded_dataset.dataset_id}/leakage-audit",
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "AUTHORIZATION_FAILED"


async def test_regular_user_cannot_create_evaluation_run(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    response = await client.post(
        "/api/v1/research/evaluations",
        headers=auth_tokens.auth_header,
        json={
            "dataset_id": str(seeded_dataset.dataset_id),
            "model_id": "smoke-baseline-cnn",
            "model_version": "0.0.1-smoke",
            "split_name": "test",
            "result_classification": "synthetic_demo",
        },
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "AUTHORIZATION_FAILED"


async def test_superuser_can_run_quality_audit(
    client: AsyncClient, superuser_auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    response = await client.post(
        f"/api/v1/research/datasets/{seeded_dataset.dataset_id}/quality-audit",
        headers=superuser_auth_tokens.auth_header,
    )
    assert response.status_code == 201, response.text


async def test_unauthenticated_request_is_rejected_before_authorization(
    client: AsyncClient, seeded_dataset: SeededDataset
) -> None:
    """No bearer token at all must fail authentication (401), not be silently treated as a
    non-admin authorization failure (403) - the two checks are independent layers."""
    response = await client.post(
        f"/api/v1/research/datasets/{seeded_dataset.dataset_id}/quality-audit"
    )
    assert response.status_code == 401, response.text

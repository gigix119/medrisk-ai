"""Integration tests for the extended GET /api/v1/predictions/history filters (Phase 3).

Basic pagination/ownership tests remain in test_predictions.py; this file is specifically
about the new module/status/decision/model_version/date-range query filters.
"""

from __future__ import annotations

import io

import numpy as np
from httpx import AsyncClient
from PIL import Image

from tests.integration.conftest import AuthTokens

HISTOPATHOLOGY_ENDPOINT = "/api/v1/predictions/histopathology"
HISTORY_ENDPOINT = "/api/v1/predictions/history"


def _png_bytes(seed: int = 0) -> bytes:
    pixels = np.random.default_rng(seed).integers(0, 256, size=(32, 32, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


async def _create_prediction(client: AsyncClient, auth_tokens: AuthTokens, *, seed: int = 0) -> str:
    response = await client.post(
        HISTOPATHOLOGY_ENDPOINT,
        files={"file": ("patch.png", _png_bytes(seed), "image/png")},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 201, response.text
    prediction_id: str = response.json()["prediction_id"]
    return prediction_id


async def test_filter_by_module(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    await _create_prediction(client, auth_tokens)

    matching = await client.get(
        f"{HISTORY_ENDPOINT}?module=histopathology", headers=auth_tokens.auth_header
    )
    non_matching = await client.get(
        f"{HISTORY_ENDPOINT}?module=survival", headers=auth_tokens.auth_header
    )

    assert matching.json()["total"] == 1
    assert non_matching.json()["total"] == 0


async def test_filter_by_status(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    await _create_prediction(client, auth_tokens)

    matching = await client.get(
        f"{HISTORY_ENDPOINT}?status=review_required", headers=auth_tokens.auth_header
    )
    non_matching = await client.get(
        f"{HISTORY_ENDPOINT}?status=completed", headers=auth_tokens.auth_header
    )

    assert matching.json()["total"] == 1
    assert non_matching.json()["total"] == 0


async def test_filter_by_decision(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    await _create_prediction(client, auth_tokens)

    matching = await client.get(
        f"{HISTORY_ENDPOINT}?decision=review_required", headers=auth_tokens.auth_header
    )
    non_matching = await client.get(
        f"{HISTORY_ENDPOINT}?decision=positive", headers=auth_tokens.auth_header
    )

    assert matching.json()["total"] == 1
    assert non_matching.json()["total"] == 0


async def test_filter_by_model_version(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    await _create_prediction(client, auth_tokens)

    matching = await client.get(
        f"{HISTORY_ENDPOINT}?model_version=0.0.1-test", headers=auth_tokens.auth_header
    )
    non_matching = await client.get(
        f"{HISTORY_ENDPOINT}?model_version=9.9.9-does-not-exist", headers=auth_tokens.auth_header
    )

    assert matching.json()["total"] == 1
    assert non_matching.json()["total"] == 0


async def test_filter_by_date_range(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    await _create_prediction(client, auth_tokens)

    in_range = await client.get(
        f"{HISTORY_ENDPOINT}?created_from=2020-01-01T00:00:00Z", headers=auth_tokens.auth_header
    )
    out_of_range = await client.get(
        f"{HISTORY_ENDPOINT}?created_to=2020-01-01T00:00:00Z", headers=auth_tokens.auth_header
    )

    assert in_range.json()["total"] == 1
    assert out_of_range.json()["total"] == 0


async def test_filters_compose_with_pagination(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    for seed in range(3):
        await _create_prediction(client, auth_tokens, seed=seed)

    response = await client.get(
        f"{HISTORY_ENDPOINT}?status=review_required&limit=2&offset=1",
        headers=auth_tokens.auth_header,
    )
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 1


async def test_ordering_is_newest_first_and_stable(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    ids = [await _create_prediction(client, auth_tokens, seed=seed) for seed in range(3)]

    response = await client.get(HISTORY_ENDPOINT, headers=auth_tokens.auth_header)
    returned_ids = [item["id"] for item in response.json()["items"]]
    assert returned_ids == list(reversed(ids))


async def test_max_limit_is_enforced(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    response = await client.get(f"{HISTORY_ENDPOINT}?limit=1000", headers=auth_tokens.auth_header)
    assert response.status_code == 422

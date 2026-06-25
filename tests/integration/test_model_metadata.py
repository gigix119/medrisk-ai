"""Integration tests for GET /api/v1/models/active."""

from __future__ import annotations

from httpx import AsyncClient

from tests.integration.conftest import AuthTokens

ENDPOINT = "/api/v1/models/active"


async def test_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(ENDPOINT)
    assert response.status_code == 401


async def test_authenticated_user_receives_safe_metadata(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    response = await client.get(ENDPOINT, headers=auth_tokens.auth_header)

    assert response.status_code == 200
    body = response.json()
    assert body["module"] == "histopathology"
    assert body["architecture"] == "baseline_cnn"
    assert body["synthetic_only"] is True
    assert body["eligible_for_demo"] is False
    assert body["input_contract"] == {"input_height": 32, "input_width": 32, "input_channels": 3}
    assert body["class_names"] == ["negative", "positive"]
    assert body["positive_class"] == "positive"
    assert body["review_policy"] == {
        "negative_probability_max": 0.3,
        "positive_probability_min": 0.7,
    }
    assert body["calibration_enabled"] is False
    assert "not a medical device" in body["disclaimer"]


async def test_response_never_includes_bundle_path(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    response = await client.get(ENDPOINT, headers=auth_tokens.auth_header)
    text = response.text.lower()
    assert "bundle_path" not in text
    assert ".pt" not in text
    assert "appdata" not in text

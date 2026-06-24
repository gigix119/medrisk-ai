"""Integration tests for the root/liveness/readiness endpoints."""

from httpx import AsyncClient


async def test_liveness_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "medrisk-ai-api"


async def test_readiness_returns_ok_when_database_available(client: AsyncClient) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


async def test_root_endpoint_includes_disclaimer(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert "not a medical device" in body["disclaimer"]


async def test_response_includes_request_id_header(client: AsyncClient) -> None:
    response = await client.get("/health/live")

    assert "x-request-id" in response.headers

"""Integration tests for prediction placeholder endpoints and history."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.prediction import Prediction, PredictionModule, PredictionStatus
from app.repositories import user as user_repo
from tests.integration.conftest import AuthTokens

PASSWORD = "correct-horse-battery-staple"


async def test_histopathology_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/predictions/histopathology", json={})
    assert response.status_code == 401


async def test_survival_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/predictions/survival", json={})
    assert response.status_code == 401


async def test_history_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/predictions/history")
    assert response.status_code == 401


async def test_authenticated_survival_returns_honest_501(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    response = await client.post(
        "/api/v1/predictions/survival", json={}, headers=auth_tokens.auth_header
    )

    assert response.status_code == 501
    body = response.json()
    assert body["module"] == "survival"
    assert "no survival model is loaded" in body["message"]


async def test_history_is_empty_for_new_user(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    response = await client.get("/api/v1/predictions/history", headers=auth_tokens.auth_header)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


async def test_history_only_returns_current_users_records(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Phase 1 never creates predictions through the API, so rows are seeded directly."""
    user_a = await user_repo.create(
        db_session,
        email="user-a@example.com",
        hashed_password=hash_password(PASSWORD),
        full_name="User A",
    )
    await user_repo.create(
        db_session,
        email="user-b@example.com",
        hashed_password=hash_password(PASSWORD),
        full_name="User B",
    )
    db_session.add(
        Prediction(
            user_id=user_a.id,
            module=PredictionModule.HISTOPATHOLOGY,
            status=PredictionStatus.PENDING,
        )
    )
    await db_session.commit()

    login_a = await client.post(
        "/api/v1/auth/login", data={"username": "user-a@example.com", "password": PASSWORD}
    )
    login_b = await client.post(
        "/api/v1/auth/login", data={"username": "user-b@example.com", "password": PASSWORD}
    )

    history_a = await client.get(
        "/api/v1/predictions/history",
        headers={"Authorization": f"Bearer {login_a.json()['access_token']}"},
    )
    history_b = await client.get(
        "/api/v1/predictions/history",
        headers={"Authorization": f"Bearer {login_b.json()['access_token']}"},
    )

    assert history_a.json()["total"] == 1
    assert len(history_a.json()["items"]) == 1
    assert history_b.json()["total"] == 0
    assert history_b.json()["items"] == []


async def test_history_pagination_parameters(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    response = await client.get(
        "/api/v1/predictions/history?limit=5&offset=10", headers=auth_tokens.auth_header
    )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 5
    assert body["offset"] == 10

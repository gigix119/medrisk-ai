"""Integration tests for the authenticated user's own profile endpoint."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.repositories import user as user_repo
from tests.integration.conftest import AuthTokens, RegisteredUser


async def test_get_me_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


async def test_get_me_with_malformed_token_returns_401(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert response.status_code == 401


async def test_get_me_with_valid_access_token_returns_current_user(
    client: AsyncClient, registered_user: RegisteredUser, auth_tokens: AuthTokens
) -> None:
    response = await client.get("/api/v1/users/me", headers=auth_tokens.auth_header)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(registered_user.id)
    assert body["email"] == registered_user.email
    assert body["full_name"] == registered_user.full_name
    assert "hashed_password" not in body


async def test_get_me_with_refresh_token_instead_of_access_token_returns_401(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {auth_tokens.refresh_token}"},
    )
    assert response.status_code == 401


async def test_get_me_with_non_uuid_subject_claim_returns_401(client: AsyncClient) -> None:
    """A well-signed token whose `sub` isn't a UUID at all (e.g. secret leaked/misused)."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": "not-a-uuid",
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm=settings.JWT_ALGORITHM
    )

    response = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_get_me_fails_for_deactivated_user(
    client: AsyncClient,
    registered_user: RegisteredUser,
    auth_tokens: AuthTokens,
    db_session: AsyncSession,
) -> None:
    user = await user_repo.get_by_email(db_session, registered_user.email)
    assert user is not None
    user.is_active = False
    await db_session.commit()

    response = await client.get("/api/v1/users/me", headers=auth_tokens.auth_header)
    assert response.status_code == 401

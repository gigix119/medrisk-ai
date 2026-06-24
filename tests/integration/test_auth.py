"""Integration tests for registration, login, refresh rotation, and logout."""

import uuid

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_refresh_token, hash_password
from app.repositories import user as user_repo
from tests.integration.conftest import AuthTokens, RegisteredUser

PASSWORD = "correct-horse-battery-staple"


def _expired_refresh_token() -> str:
    """A structurally valid refresh JWT whose exp claim is already in the past."""
    settings = get_settings()
    expired_settings = settings.model_copy(update={"JWT_REFRESH_TOKEN_EXPIRE_DAYS": -1})
    issued = create_refresh_token(expired_settings, user_id=uuid.uuid4())
    return issued.token


# --- Registration ---


async def test_register_returns_201_with_safe_user_payload(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "New.User@Example.com", "password": PASSWORD, "full_name": "New User"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.user@example.com"
    assert body["is_active"] is True
    assert body["is_superuser"] is False
    assert "hashed_password" not in body
    assert "password" not in body


async def test_register_duplicate_email_returns_409(
    client: AsyncClient, registered_user: RegisteredUser
) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": registered_user.email, "password": PASSWORD, "full_name": "Someone Else"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_register_invalid_email_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": PASSWORD, "full_name": "Someone"},
    )

    assert response.status_code == 422


async def test_register_too_short_password_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "short.pw@example.com", "password": "tooshort", "full_name": "Someone"},
    )

    assert response.status_code == 422


# --- Login ---


async def test_login_with_valid_credentials_returns_token_pair(
    client: AsyncClient, registered_user: RegisteredUser
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": registered_user.email, "password": registered_user.password},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


async def test_login_with_wrong_password_returns_401(
    client: AsyncClient, registered_user: RegisteredUser
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": registered_user.email, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_FAILED"


async def test_login_with_nonexistent_email_returns_same_generic_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "nobody@example.com", "password": "whatever-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_FAILED"
    assert response.json()["error"]["message"] == "Invalid email or password."


async def test_inactive_user_cannot_log_in(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await user_repo.create(
        db_session,
        email="inactive@example.com",
        hashed_password=hash_password(PASSWORD),
        full_name="Inactive User",
    )
    user.is_active = False
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "inactive@example.com", "password": PASSWORD},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


# --- Refresh rotation ---


async def test_valid_refresh_token_creates_new_token_pair(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": auth_tokens.refresh_token}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["refresh_token"] != auth_tokens.refresh_token


async def test_old_refresh_token_is_revoked_after_rotation(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    await client.post("/api/v1/auth/refresh", json={"refresh_token": auth_tokens.refresh_token})

    reuse_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": auth_tokens.refresh_token}
    )

    assert reuse_response.status_code == 401
    assert reuse_response.json()["error"]["code"] == "TOKEN_REVOKED"


async def test_expired_refresh_token_fails(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": _expired_refresh_token()}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


async def test_malformed_refresh_token_fails(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"})

    assert response.status_code == 401


async def test_refresh_with_well_signed_but_unknown_jti_fails(client: AsyncClient) -> None:
    """A structurally/cryptographically valid token with no matching DB session."""
    settings = get_settings()
    issued = create_refresh_token(settings, user_id=uuid.uuid4())

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": issued.token})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_FAILED"


async def test_refresh_with_tampered_stored_hash_fails(
    client: AsyncClient, auth_tokens: AuthTokens, db_session: AsyncSession
) -> None:
    """Defense in depth: even a structurally valid token must match its stored fingerprint."""
    await db_session.execute(text("UPDATE refresh_token_sessions SET token_hash = 'deadbeef'"))
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": auth_tokens.refresh_token}
    )

    assert response.status_code == 401


async def test_refresh_fails_for_deactivated_user(
    client: AsyncClient,
    registered_user: RegisteredUser,
    auth_tokens: AuthTokens,
    db_session: AsyncSession,
) -> None:
    user = await user_repo.get_by_email(db_session, registered_user.email)
    assert user is not None
    user.is_active = False
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": auth_tokens.refresh_token}
    )

    assert response.status_code == 401


# --- Logout ---


async def test_logout_revokes_refresh_session(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    logout_response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": auth_tokens.refresh_token}
    )
    assert logout_response.status_code == 204

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": auth_tokens.refresh_token}
    )
    assert refresh_response.status_code == 401
    assert refresh_response.json()["error"]["code"] == "TOKEN_REVOKED"


async def test_repeated_logout_is_handled_safely(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    first = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": auth_tokens.refresh_token}
    )
    second = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": auth_tokens.refresh_token}
    )

    assert first.status_code == 204
    assert second.status_code == 204


async def test_logout_with_malformed_token_is_handled_safely(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/logout", json={"refresh_token": "garbage"})
    assert response.status_code == 204

"""Unit tests for app.core.security: password hashing and JWT issuance/verification."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, TokenExpiredError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)


def _settings(**overrides: object) -> Settings:
    kwargs: dict[str, object] = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
        "TEST_DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db_test",
        "POSTGRES_PASSWORD": "irrelevant",
        "JWT_SECRET_KEY": "a" * 64,
        "JWT_ISSUER": "medrisk-ai-tests",
        "JWT_AUDIENCE": "medrisk-ai-tests-clients",
    }
    kwargs.update(overrides)
    return Settings(**kwargs)


# --- Password hashing ---


def test_hash_password_differs_from_plaintext() -> None:
    hashed = hash_password("a-very-secret-password")
    assert hashed != "a-very-secret-password"


def test_verify_password_succeeds_for_correct_password() -> None:
    hashed = hash_password("a-very-secret-password")
    assert verify_password("a-very-secret-password", hashed) is True


def test_verify_password_fails_for_incorrect_password() -> None:
    hashed = hash_password("a-very-secret-password")
    assert verify_password("wrong-password", hashed) is False


def test_hash_token_is_deterministic_sha256() -> None:
    assert hash_token("raw-token-value") == hash_token("raw-token-value")
    assert hash_token("raw-token-value") != hash_token("different-token-value")


# --- JWT ---


def test_valid_access_token_decodes() -> None:
    settings = _settings()
    user_id = uuid.uuid4()
    issued = create_access_token(settings, user_id=user_id)

    decoded = decode_token(settings, issued.token, expected_type="access")

    assert decoded.sub == str(user_id)
    assert decoded.type == "access"
    assert decoded.jti == issued.jti


def test_valid_refresh_token_decodes() -> None:
    settings = _settings()
    issued = create_refresh_token(settings, user_id=uuid.uuid4())

    decoded = decode_token(settings, issued.token, expected_type="refresh")

    assert decoded.type == "refresh"


def test_expired_token_is_rejected() -> None:
    settings = _settings(JWT_ACCESS_TOKEN_EXPIRE_MINUTES=0)
    issued = create_access_token(settings, user_id=uuid.uuid4())

    with pytest.raises(TokenExpiredError):
        decode_token(settings, issued.token, expected_type="access")


def test_wrong_issuer_is_rejected() -> None:
    issuing_settings = _settings(JWT_ISSUER="issuer-a")
    verifying_settings = _settings(JWT_ISSUER="issuer-b")
    issued = create_access_token(issuing_settings, user_id=uuid.uuid4())

    with pytest.raises(AuthenticationError):
        decode_token(verifying_settings, issued.token, expected_type="access")


def test_wrong_audience_is_rejected() -> None:
    issuing_settings = _settings(JWT_AUDIENCE="aud-a")
    verifying_settings = _settings(JWT_AUDIENCE="aud-b")
    issued = create_access_token(issuing_settings, user_id=uuid.uuid4())

    with pytest.raises(AuthenticationError):
        decode_token(verifying_settings, issued.token, expected_type="access")


def test_wrong_token_type_is_rejected() -> None:
    settings = _settings()
    issued = create_refresh_token(settings, user_id=uuid.uuid4())

    with pytest.raises(AuthenticationError):
        decode_token(settings, issued.token, expected_type="access")


def test_malformed_token_is_rejected() -> None:
    settings = _settings()

    with pytest.raises(AuthenticationError):
        decode_token(settings, "this-is-not-a-jwt", expected_type="access")


def test_tampered_signature_is_rejected() -> None:
    settings = _settings()
    issued = create_access_token(settings, user_id=uuid.uuid4())
    header, payload, signature = issued.token.split(".")
    # Flip 4 base64url characters (not just 1) so the decoded signature bytes
    # are guaranteed to differ - a single trailing base64 char can have
    # "don't care" bits that decode to the same byte.
    flipped_tail = "AAAA" if signature[-4:] != "AAAA" else "BBBB"
    tampered = f"{header}.{payload}.{signature[:-4] + flipped_tail}"

    with pytest.raises(AuthenticationError):
        decode_token(settings, tampered, expected_type="access")


def test_token_missing_required_claim_is_rejected() -> None:
    settings = _settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        # "jti" deliberately omitted
    }
    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm=settings.JWT_ALGORITHM
    )

    with pytest.raises(AuthenticationError):
        decode_token(settings, token, expected_type="access")

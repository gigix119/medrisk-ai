"""Password hashing (Argon2 via pwdlib) and JWT issuance/verification (PyJWT).

All functions take an explicit `Settings` argument instead of importing a
global settings singleton, so they stay easy to unit test with custom
secrets/issuers/expiries.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, TokenExpiredError

_password_hasher = PasswordHash([Argon2Hasher()])

TokenType = Literal["access", "refresh"]

_REQUIRED_CLAIMS = ["sub", "type", "iat", "exp", "iss", "aud", "jti"]


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password with Argon2. Never store the plaintext itself."""
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a previously hashed value."""
    return _password_hasher.verify(plain_password, hashed_password)


def hash_token(raw_token: str) -> str:
    """One-way SHA-256 fingerprint of a raw token, for at-rest storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IssuedToken:
    """A freshly created JWT, plus the metadata needed to track/revoke it."""

    token: str
    jti: str
    expires_at: datetime


@dataclass(frozen=True)
class DecodedToken:
    """A verified JWT payload, narrowed to the claims the application relies on."""

    sub: str
    type: TokenType
    jti: str
    issued_at: datetime
    expires_at: datetime


def _issue_token(
    settings: Settings,
    *,
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
) -> IssuedToken:
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    jti = uuid.uuid4().hex

    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": jti,
    }
    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm=settings.JWT_ALGORITHM
    )
    return IssuedToken(token=token, jti=jti, expires_at=expires_at)


def create_access_token(settings: Settings, *, user_id: uuid.UUID) -> IssuedToken:
    return _issue_token(
        settings,
        subject=str(user_id),
        token_type="access",
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(settings: Settings, *, user_id: uuid.UUID) -> IssuedToken:
    return _issue_token(
        settings,
        subject=str(user_id),
        token_type="refresh",
        expires_delta=timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(settings: Settings, token: str, *, expected_type: TokenType) -> DecodedToken:
    """Decode and fully verify a JWT: signature, expiry, issuer, audience, required claims.

    Raises AuthenticationError (or TokenExpiredError) on any failure. Callers
    must not branch on jwt-library-specific exceptions themselves.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={"require": _REQUIRED_CLAIMS},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid authentication token.") from exc

    if payload.get("type") != expected_type:
        raise AuthenticationError(f"Expected a '{expected_type}' token.")

    return DecodedToken(
        sub=payload["sub"],
        type=payload["type"],
        jti=payload["jti"],
        issued_at=datetime.fromtimestamp(payload["iat"], tz=UTC),
        expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
    )

"""Authentication business logic: registration, login, refresh rotation, logout.

Transaction boundary: this module calls session.commit(). Repositories only
add()/flush(); they never commit, so each function below executes as one
atomic unit of work.
"""

import hmac
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ConflictError, TokenRevokedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.user import User
from app.repositories import refresh_token as refresh_token_repo
from app.repositories import user as user_repo


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


async def register_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str,
) -> User:
    normalized_email = email.strip().lower()
    existing = await user_repo.get_by_email(session, normalized_email)
    if existing is not None:
        raise ConflictError("A user with this email already exists.", details={"field": "email"})

    user = await user_repo.create(
        session,
        email=normalized_email,
        hashed_password=hash_password(password),
        full_name=full_name,
    )
    await session.commit()
    return user


async def authenticate_user(session: AsyncSession, *, email: str, password: str) -> User:
    """Verify credentials. Raises the same generic AuthenticationError in every failure case."""
    normalized_email = email.strip().lower()
    user = await user_repo.get_by_email(session, normalized_email)
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthenticationError("Invalid email or password.")
    if not user.is_active:
        raise AuthenticationError("Invalid email or password.")
    return user


async def issue_token_pair(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
    user_agent: str | None,
    ip_address: str | None,
) -> TokenPair:
    """Issue a fresh access+refresh token pair and persist the refresh session."""
    access = create_access_token(settings, user_id=user.id)
    refresh = create_refresh_token(settings, user_id=user.id)

    await refresh_token_repo.create(
        session,
        user_id=user.id,
        jti=refresh.jti,
        token_hash=hash_token(refresh.token),
        expires_at=refresh.expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    await session.commit()

    return TokenPair(
        access_token=access.token,
        refresh_token=refresh.token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def login(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    password: str,
    user_agent: str | None,
    ip_address: str | None,
) -> TokenPair:
    user = await authenticate_user(session, email=email, password=password)
    return await issue_token_pair(
        session, settings, user=user, user_agent=user_agent, ip_address=ip_address
    )


async def rotate_refresh_token(
    session: AsyncSession,
    settings: Settings,
    *,
    raw_refresh_token: str,
    user_agent: str | None,
    ip_address: str | None,
) -> TokenPair:
    """Validate + rotate a refresh token. Reuse of an already-rotated token fails."""
    decoded = decode_token(settings, raw_refresh_token, expected_type="refresh")

    stored_session = await refresh_token_repo.get_by_jti(session, decoded.jti)
    if stored_session is None:
        raise AuthenticationError("Invalid refresh token.")

    if not hmac.compare_digest(stored_session.token_hash, hash_token(raw_refresh_token)):
        raise AuthenticationError("Invalid refresh token.")

    if stored_session.revoked_at is not None:
        raise TokenRevokedError("This refresh token has already been used or revoked.")

    user = await user_repo.get_by_id(session, stored_session.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid refresh token.")

    access = create_access_token(settings, user_id=user.id)
    new_refresh = create_refresh_token(settings, user_id=user.id)

    await refresh_token_repo.revoke(session, stored_session, replaced_by_jti=new_refresh.jti)
    await refresh_token_repo.mark_used(session, stored_session)
    await refresh_token_repo.create(
        session,
        user_id=user.id,
        jti=new_refresh.jti,
        token_hash=hash_token(new_refresh.token),
        expires_at=new_refresh.expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    await session.commit()

    return TokenPair(
        access_token=access.token,
        refresh_token=new_refresh.token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def logout(session: AsyncSession, settings: Settings, *, raw_refresh_token: str) -> None:
    """Revoke the session behind this refresh token. Idempotent and detail-free on failure."""
    try:
        decoded = decode_token(settings, raw_refresh_token, expected_type="refresh")
    except AuthenticationError:
        return

    stored_session = await refresh_token_repo.get_by_jti(session, decoded.jti)
    if stored_session is None or stored_session.revoked_at is not None:
        return

    await refresh_token_repo.revoke(session, stored_session)
    await session.commit()


async def get_authenticated_user(
    session: AsyncSession, settings: Settings, *, access_token: str
) -> User:
    """Resolve the User behind a bearer access token, for the get_current_user dependency."""
    decoded = decode_token(settings, access_token, expected_type="access")
    try:
        user_id = uuid.UUID(decoded.sub)
    except ValueError as exc:
        raise AuthenticationError("Invalid authentication token.") from exc

    user = await user_repo.get_by_id(session, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid authentication token.")
    return user

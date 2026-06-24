"""Database access for refresh-token sessions (rotation / revocation tracking)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshTokenSession


async def create(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    jti: str,
    token_hash: str,
    expires_at: datetime,
    user_agent: str | None,
    ip_address: str | None,
) -> RefreshTokenSession:
    refresh_session = RefreshTokenSession(
        user_id=user_id,
        jti=jti,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    session.add(refresh_session)
    await session.flush()
    return refresh_session


async def get_by_jti(session: AsyncSession, jti: str) -> RefreshTokenSession | None:
    result = await session.execute(
        select(RefreshTokenSession).where(RefreshTokenSession.jti == jti)
    )
    return result.scalar_one_or_none()


async def revoke(
    session: AsyncSession,
    refresh_session: RefreshTokenSession,
    *,
    replaced_by_jti: str | None = None,
) -> None:
    refresh_session.revoked_at = datetime.now(UTC)
    refresh_session.replaced_by_jti = replaced_by_jti
    await session.flush()


async def mark_used(session: AsyncSession, refresh_session: RefreshTokenSession) -> None:
    refresh_session.last_used_at = datetime.now(UTC)
    await session.flush()

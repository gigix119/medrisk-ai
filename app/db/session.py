"""Async SQLAlchemy engine and per-request session management.

There is exactly one Engine per process (it owns the connection pool and is
safe to share). There is NEVER a shared AsyncSession: every request gets its
own, created fresh by the get_db_session FastAPI dependency and closed at
the end of that request.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings


def get_database_url(settings: Settings) -> str:
    """Pick the database URL for the current environment.

    The test environment uses a separate database (TEST_DATABASE_URL) so
    integration tests never read or write development data. Alembic reuses
    this exact function, so running it with ENVIRONMENT=test migrates the
    test database instead of the development one.
    """
    if settings.ENVIRONMENT == "test":
        return settings.TEST_DATABASE_URL
    return settings.DATABASE_URL


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(get_database_url(settings), pool_pre_ping=True)


engine: AsyncEngine = create_engine(get_settings())

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a request-scoped AsyncSession.

    Rolls back automatically if the request raised, and always closes the
    session afterward. Callers (the service layer) are responsible for
    calling commit() when a unit of work succeeds.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

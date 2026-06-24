"""Fixtures shared by integration tests: DB session, async HTTP client, test users."""

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.main import app

_TEST_TABLES = "refresh_token_sessions, predictions, users"


@pytest_asyncio.fixture(autouse=True)
async def _clean_database_after_test() -> AsyncGenerator[None, None]:
    """Truncates all application tables after every integration test.

    Runs against the real test database (no mocking), so this - not a
    rolled-back transaction - is what keeps tests from leaking state into
    each other.
    """
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(text(f"TRUNCATE TABLE {_TEST_TABLES} RESTART IDENTITY CASCADE"))
        await session.commit()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """A standalone session for tests that need to set up or assert on DB rows directly."""
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """An async HTTP client driving the real app in-process (ASGI transport, no sockets).

    base_url uses "localhost" (not httpx's default "testserver") so requests
    pass the app's TrustedHostMiddleware, which only allows ALLOWED_HOSTS.
    """
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost") as ac:
            yield ac


@dataclass(frozen=True)
class RegisteredUser:
    id: uuid.UUID
    email: str
    password: str
    full_name: str


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> RegisteredUser:
    """Registers a fresh user through the real /auth/register endpoint."""
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    password = "correct-horse-battery-staple"
    full_name = "Test User"

    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return RegisteredUser(
        id=uuid.UUID(body["id"]), email=email, password=password, full_name=full_name
    )


@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    refresh_token: str

    @property
    def auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}


@pytest_asyncio.fixture
async def auth_tokens(client: AsyncClient, registered_user: RegisteredUser) -> AuthTokens:
    """Logs in the `registered_user` fixture and returns a fresh token pair."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": registered_user.email, "password": registered_user.password},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return AuthTokens(access_token=body["access_token"], refresh_token=body["refresh_token"])

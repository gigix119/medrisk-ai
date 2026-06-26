"""Fixtures shared by integration tests: DB session, async HTTP client, test users."""

import io
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import numpy as np
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.user import User
from app.repositories import dataset as dataset_repo
from tests.conftest import TEST_DATASETS_ROOT

_TEST_TABLES = (
    "refresh_token_sessions, evaluation_sample_predictions, evaluation_runs, experiment_runs, "
    "dataset_quality_audits, dataset_leakage_audits, research_studies, predictions, "
    "model_deployments, dataset_samples, datasets, users"
)


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


@pytest_asyncio.fixture
async def superuser_auth_tokens(client: AsyncClient, db_session: AsyncSession) -> AuthTokens:
    """Registers a fresh user through the normal `/auth/register` flow, then promotes it to
    `is_superuser=True` directly via the database (there is no API for this - promoting an
    administrator is an operator action, see scripts/promote_superuser.py), and logs in.

    Used by tests that exercise the admin-only research write endpoints
    (POST .../quality-audit, .../leakage-audit, .../evaluations - see
    app.api.dependencies.CurrentSuperuserDep).
    """
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    password = "correct-horse-battery-staple"
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Admin User"},
    )
    assert register_response.status_code == 201, register_response.text
    user_id = uuid.UUID(register_response.json()["id"])

    await db_session.execute(update(User).where(User.id == user_id).values(is_superuser=True))
    await db_session.commit()

    login_response = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    assert login_response.status_code == 200, login_response.text
    body = login_response.json()
    return AuthTokens(access_token=body["access_token"], refresh_token=body["refresh_token"])


def _png_bytes(size: int, *, bright: bool) -> bytes:
    """A tiny real PNG matching the session-wide test model's 32x32 input contract (see
    tests/conftest.py) - content doesn't matter to that constant-output model, only that it
    decodes as a valid same-size image."""
    fill = 220 if bright else 40
    pixels = np.full((size, size, 3), fill, dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


@dataclass(frozen=True)
class SeededDataset:
    dataset_id: uuid.UUID
    negative_sample_id: uuid.UUID
    positive_sample_id: uuid.UUID


@pytest_asyncio.fixture
async def seeded_dataset(db_session: AsyncSession) -> SeededDataset:
    """Inserts one dataset + two samples (one per class) directly via the repository layer,
    with real 32x32 PNGs written under the session-wide TEST_DATASETS_ROOT (matching
    Settings.DATASETS_ROOT for the test process - see tests/conftest.py)."""
    slug = f"test-dataset-{uuid.uuid4().hex[:8]}"
    version = "1.0.0"
    image_root = TEST_DATASETS_ROOT / slug / version / "images"
    image_root.mkdir(parents=True)

    dataset = await dataset_repo.upsert_dataset(
        db_session,
        slug=slug,
        name="Test Dataset",
        version=version,
        description="Fixture dataset for integration tests.",
        source_name="test-fixture",
        source_url=None,
        license_name="N/A",
        license_url=None,
        citation=None,
        intended_use="Testing only.",
        prohibited_use="N/A",
        modality="histopathology_patch",
        task_type="binary_classification",
        classes=["negative", "positive"],
        sample_count=2,
        image_width=32,
        image_height=32,
        image_channels=3,
        split_names=["train"],
        class_distribution={"train": {"negative": 1, "positive": 1}},
        preprocessing_summary=None,
        known_limitations="Synthetic test fixture.",
        ethical_notes="No real data involved.",
        is_synthetic=True,
        is_public=True,
        is_active=True,
    )

    negative_path = image_root / "negative.png"
    negative_path.write_bytes(_png_bytes(32, bright=False))
    negative_sample = await dataset_repo.upsert_sample(
        db_session,
        dataset_id=dataset.id,
        sample_key="negative-001",
        split="train",
        filename="negative.png",
        relative_path="images/negative.png",
        ground_truth_label="negative",
        class_index=0,
        width=32,
        height=32,
        mime_type="image/png",
        checksum_sha256="0" * 64,
        source_reference=None,
        license_reference=None,
        is_synthetic=True,
        metadata_json=None,
        notes=None,
    )

    positive_path = image_root / "positive.png"
    positive_path.write_bytes(_png_bytes(32, bright=True))
    positive_sample = await dataset_repo.upsert_sample(
        db_session,
        dataset_id=dataset.id,
        sample_key="positive-001",
        split="train",
        filename="positive.png",
        relative_path="images/positive.png",
        ground_truth_label="positive",
        class_index=1,
        width=32,
        height=32,
        mime_type="image/png",
        checksum_sha256="1" * 64,
        source_reference=None,
        license_reference=None,
        is_synthetic=True,
        metadata_json=None,
        notes=None,
    )
    await db_session.commit()

    return SeededDataset(
        dataset_id=dataset.id,
        negative_sample_id=negative_sample.id,
        positive_sample_id=positive_sample.id,
    )

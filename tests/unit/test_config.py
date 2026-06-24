"""Unit tests for app.core.config.Settings.

These construct Settings directly with explicit kwargs rather than going
through get_settings(), so each test is isolated from both the cache and
the developer's real .env file.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _base_kwargs(**overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
        "TEST_DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db_test",
        "POSTGRES_PASSWORD": "irrelevant",
        "JWT_SECRET_KEY": "a" * 64,
    }
    kwargs.update(overrides)
    return kwargs


def test_settings_load_correctly_in_test_mode() -> None:
    settings = Settings(**_base_kwargs(ENVIRONMENT="test", JWT_SECRET_KEY="short-secret"))

    assert settings.ENVIRONMENT == "test"
    assert settings.JWT_SECRET_KEY.get_secret_value() == "short-secret"


@pytest.mark.parametrize("environment", ["development", "production"])
def test_insecure_jwt_secret_is_rejected_outside_test(environment: str) -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(**_base_kwargs(ENVIRONMENT=environment, JWT_SECRET_KEY="changeme"))


@pytest.mark.parametrize("environment", ["development", "production"])
def test_missing_jwt_secret_is_rejected_outside_test(environment: str) -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(**_base_kwargs(ENVIRONMENT=environment, JWT_SECRET_KEY=""))


def test_empty_jwt_secret_is_rejected_even_in_test_mode() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(**_base_kwargs(ENVIRONMENT="test", JWT_SECRET_KEY=""))


def test_strong_jwt_secret_is_accepted_in_production() -> None:
    settings = Settings(**_base_kwargs(ENVIRONMENT="production", JWT_SECRET_KEY="x" * 64))
    assert settings.ENVIRONMENT == "production"


def test_cors_origins_parsed_from_comma_separated_string() -> None:
    settings = Settings(
        **_base_kwargs(
            ENVIRONMENT="test",
            CORS_ORIGINS="http://localhost:3000, http://localhost:8000",
        )
    )
    assert settings.CORS_ORIGINS == ["http://localhost:3000", "http://localhost:8000"]


def test_allowed_hosts_parsed_from_comma_separated_string() -> None:
    settings = Settings(
        **_base_kwargs(ENVIRONMENT="test", ALLOWED_HOSTS="example.com, api.example.com")
    )
    assert settings.ALLOWED_HOSTS == ["example.com", "api.example.com"]


def test_cors_origins_empty_string_parses_to_empty_list() -> None:
    settings = Settings(**_base_kwargs(ENVIRONMENT="test", CORS_ORIGINS=""))
    assert settings.CORS_ORIGINS == []


def test_database_url_must_use_asyncpg_scheme() -> None:
    with pytest.raises(ValidationError, match=r"postgresql\+asyncpg"):
        Settings(
            **_base_kwargs(
                ENVIRONMENT="test",
                DATABASE_URL="postgresql://user:pass@localhost:5432/db",
            )
        )

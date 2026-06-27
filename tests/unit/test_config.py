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
        # Explicit, env-var-independent baseline: tests/conftest.py sets these as real OS
        # env vars for the integration test session's model bundle (see that file's
        # docstring), and pydantic-settings reads env vars for any field not passed here -
        # without this, these tests would silently pick up that ambient state instead of
        # the framework defaults they intend to exercise.
        "MODEL_REQUIRED": False,
        "MODEL_BUNDLE_PATH": None,
        "ALLOW_SYNTHETIC_MODEL": False,
        "DEV_SEED_USER_EMAIL": None,
        "DEV_SEED_USER_PASSWORD": None,
        # Same reasoning: tests/conftest.py also forces RATE_LIMIT_ENABLED=false as a real
        # env var for the whole session, so pin it back to the framework default here too.
        "RATE_LIMIT_ENABLED": True,
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
    settings = Settings(
        **_base_kwargs(ENVIRONMENT="production", JWT_SECRET_KEY="x" * 64, MODEL_REQUIRED=True)
    )
    assert settings.ENVIRONMENT == "production"


def test_production_requires_model_required_true() -> None:
    with pytest.raises(ValidationError, match="MODEL_REQUIRED"):
        Settings(
            **_base_kwargs(ENVIRONMENT="production", JWT_SECRET_KEY="x" * 64, MODEL_REQUIRED=False)
        )


def test_production_rejects_allow_synthetic_model() -> None:
    with pytest.raises(ValidationError, match="ALLOW_SYNTHETIC_MODEL"):
        Settings(
            **_base_kwargs(
                ENVIRONMENT="production",
                JWT_SECRET_KEY="x" * 64,
                MODEL_REQUIRED=True,
                ALLOW_SYNTHETIC_MODEL=True,
            )
        )


def test_production_rejects_dev_seed_user_email() -> None:
    with pytest.raises(ValidationError, match="DEV_SEED_USER"):
        Settings(
            **_base_kwargs(
                ENVIRONMENT="production",
                JWT_SECRET_KEY="x" * 64,
                MODEL_REQUIRED=True,
                DEV_SEED_USER_EMAIL="dev@example.com",
            )
        )


def test_development_accepts_dev_seed_user_credentials() -> None:
    settings = Settings(
        **_base_kwargs(
            ENVIRONMENT="development",
            JWT_SECRET_KEY="x" * 64,
            DEV_SEED_USER_EMAIL="dev@example.com",
            DEV_SEED_USER_PASSWORD="some-password",
        )
    )
    assert settings.DEV_SEED_USER_EMAIL == "dev@example.com"


def test_development_does_not_require_model_required() -> None:
    settings = Settings(**_base_kwargs(ENVIRONMENT="development", JWT_SECRET_KEY="x" * 64))
    assert settings.MODEL_REQUIRED is False


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


def test_database_url_accepts_asyncpg_scheme_unchanged() -> None:
    settings = Settings(
        **_base_kwargs(
            ENVIRONMENT="test",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
        )
    )
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost:5432/db"


def test_database_url_normalizes_postgresql_scheme() -> None:
    settings = Settings(
        **_base_kwargs(
            ENVIRONMENT="test",
            DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        )
    )
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost:5432/db"


def test_database_url_normalizes_postgres_scheme() -> None:
    settings = Settings(
        **_base_kwargs(
            ENVIRONMENT="test",
            DATABASE_URL="postgres://user:pass@localhost:5432/db",
        )
    )
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost:5432/db"


def test_database_url_rejects_unrelated_scheme() -> None:
    with pytest.raises(ValidationError, match=r"postgresql\+asyncpg"):
        Settings(
            **_base_kwargs(
                ENVIRONMENT="test",
                DATABASE_URL="mysql://user:pass@localhost:3306/db",
            )
        )

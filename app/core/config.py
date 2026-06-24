"""Application configuration, loaded once from environment variables / .env.

Settings are intentionally typed and validated at startup: a misconfigured
deployment (e.g. a missing database URL or a weak JWT secret) should fail
immediately and loudly, rather than fail later on the first real request.
"""

from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["development", "test", "production"]

# Values that must never be accepted as a real JWT secret outside of tests.
_INSECURE_JWT_SECRETS = {
    "",
    "secret",
    "changeme",
    "change-me",
    "changeme-generate-a-real-secret-for-local-dev",
}
_MIN_JWT_SECRET_LENGTH = 32


def _split_comma_separated(value: Any) -> Any:
    """Allow list-typed settings to be supplied as a single comma-separated string."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    """Typed application settings, sourced from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "MedRisk AI"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Environment = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- Database ---
    DATABASE_URL: str
    TEST_DATABASE_URL: str

    # --- PostgreSQL service settings (used by docker compose / init scripts) ---
    POSTGRES_DB: str = "medrisk"
    POSTGRES_TEST_DB: str = "medrisk_test"
    POSTGRES_USER: str = "medrisk"
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_PORT: int = 5432

    # --- JWT ---
    JWT_SECRET_KEY: SecretStr
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ISSUER: str = "medrisk-ai"
    JWT_AUDIENCE: str = "medrisk-ai-clients"

    # --- CORS / hosts ---
    # NoDecode: these arrive as plain comma-separated strings, not JSON, so
    # pydantic-settings must not try to json.loads() them before our validator runs.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(default_factory=list)
    ALLOWED_HOSTS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1"]
    )

    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    @field_validator("CORS_ORIGINS", "ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_comma_separated_lists(cls, value: Any) -> Any:
        return _split_comma_separated(value)

    @field_validator("DATABASE_URL", "TEST_DATABASE_URL")
    @classmethod
    def validate_database_url_scheme(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "Database URL must use the 'postgresql+asyncpg://' scheme, "
                f"got: {value.split('://', 1)[0]}://..."
            )
        return value

    @model_validator(mode="after")
    def validate_jwt_secret_strength(self) -> "Settings":
        if self.ENVIRONMENT == "test":
            # The test environment may use a fixed, predictable secret so CI
            # runs are deterministic; it must still not be empty.
            if not self.JWT_SECRET_KEY.get_secret_value():
                raise ValueError("JWT_SECRET_KEY must not be empty, even in the test environment.")
            return self

        secret = self.JWT_SECRET_KEY.get_secret_value()
        if secret in _INSECURE_JWT_SECRETS or len(secret) < _MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                "JWT_SECRET_KEY is missing or insecure for environment "
                f"'{self.ENVIRONMENT}'. Generate a real secret, e.g.: "
                'python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached Settings instance.

    Cached with lru_cache so Settings (and its validation) only runs once per
    process. Tests that need different settings must call
    ``get_settings.cache_clear()`` first.
    """
    return Settings()

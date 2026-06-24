"""Liveness and readiness endpoints.

These are infrastructure routes, deliberately not versioned under /api/v1.
"""

from fastapi import APIRouter
from sqlalchemy import text

from app.api.dependencies import DbSessionDep
from app.core.exceptions import ServiceUnavailableError
from app.schemas.common import HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthStatus, summary="Liveness probe")
async def liveness() -> HealthStatus:
    """Confirms the API process itself is alive. Deliberately does not touch the database."""
    return HealthStatus(status="ok", service="medrisk-ai-api")


@router.get("/health/ready", response_model=HealthStatus, summary="Readiness probe")
async def readiness(session: DbSessionDep) -> HealthStatus:
    """Confirms required dependencies (PostgreSQL) are reachable."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        # Intentionally broad: any DB failure here (timeout, refused, auth)
        # must surface as "not ready", not as an unhandled 500.
        raise ServiceUnavailableError("Database is not reachable.") from exc
    return HealthStatus(status="ok", service="medrisk-ai-api", database="ok")

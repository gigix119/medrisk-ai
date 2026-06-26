"""Liveness, readiness, and model-health endpoints.

These are infrastructure routes, deliberately not versioned under /api/v1.
"""

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.api.dependencies import DbSessionDep, SettingsDep
from app.core.exceptions import ServiceUnavailableError
from app.schemas.common import HealthStatus, ReadinessResponse, VersionResponse
from app.schemas.model_deployment import ModelHealthInfo, ModelHealthResponse

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthStatus, summary="Liveness probe")
async def liveness() -> HealthStatus:
    """Confirms the API process itself is alive. Deliberately does not touch the database
    or the model runtime."""
    return HealthStatus(status="ok", service="medrisk-ai-api")


@router.get("/health/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def readiness(
    request: Request, session: DbSessionDep, settings: SettingsDep
) -> ReadinessResponse:
    """Readiness requires PostgreSQL, and additionally the histopathology model when
    `MODEL_REQUIRED=true`. Returns 503 (via `ServiceUnavailableError`) when not ready."""
    dependencies: dict[str, str] = {}

    try:
        await session.execute(text("SELECT 1"))
        dependencies["database"] = "ready"
    except Exception as exc:
        # Intentionally broad: any DB failure here (timeout, refused, auth) must surface
        # as "not ready", not as an unhandled 500.
        raise ServiceUnavailableError(
            "Database is not reachable.", details={"dependencies": {"database": "unreachable"}}
        ) from exc

    active = getattr(request.app.state, "histopathology_model", None)
    model_ready = active is not None and active.runtime.health().ready
    if settings.MODEL_REQUIRED:
        dependencies["histopathology_model"] = "ready" if model_ready else "not_ready"
        if not model_ready:
            raise ServiceUnavailableError(
                "Histopathology model is required but not ready.",
                details={"dependencies": dependencies},
            )
    else:
        dependencies["histopathology_model"] = "ready" if model_ready else "not_configured"

    return ReadinessResponse(status="ready", dependencies=dependencies)


@router.get("/health/model", response_model=ModelHealthResponse, summary="Model health")
async def model_health(request: Request) -> ModelHealthResponse:
    """Public, non-sensitive model runtime status - never the bundle path or other
    internal administration details."""
    active = getattr(request.app.state, "histopathology_model", None)
    if active is None:
        return ModelHealthResponse(status="unavailable", model=None)

    health = active.runtime.health()
    return ModelHealthResponse(
        status="ready" if health.ready else "unavailable",
        model=ModelHealthInfo(
            model_id=health.model_id or "",
            version=health.model_version or "",
            architecture=active.runtime.manifest.architecture,
            synthetic_only=bool(health.synthetic_only),
            device_type=health.device,
            warmup_completed=health.warmup_completed,
        ),
    )


@router.get("/version", response_model=VersionResponse, summary="Safe release metadata")
async def version(request: Request, settings: SettingsDep) -> VersionResponse:
    """Public, non-sensitive build/release info only - no environment dump, dependency list,
    filesystem path, or database host. See VersionResponse's docstring for the "never
    fabricated, only omitted" rule applied to git_commit/model_version."""
    active = getattr(request.app.state, "histopathology_model", None)
    model_health = active.runtime.health() if active is not None else None
    return VersionResponse(
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        git_commit=settings.GIT_COMMIT_SHA,
        model_version=model_health.model_version if model_health else None,
        model_synthetic_only=bool(model_health.synthetic_only) if model_health else None,
    )

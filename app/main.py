"""FastAPI application factory."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import router as api_router
from app.core.config import get_settings
from app.core.constants import MEDICAL_DISCLAIMER
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_request_id
from app.db.session import engine
from app.middleware.request_id import RequestIdMiddleware
from app.schemas.common import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


def _request_id_from(request: Request) -> str | None:
    return getattr(request.state, "request_id", None) or get_request_id()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info(
        "Starting %s v%s in '%s' environment (debug=%s)",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT,
        settings.DEBUG,
    )
    yield
    logger.info("Shutting down %s - disposing database engine.", settings.APP_NAME)
    await engine.dispose()


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=exc.error_code,
                    message=exc.message,
                    details=exc.details,
                    request_id=_request_id_from(request),
                )
            ).model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="VALIDATION_ERROR",
                    message="The request did not pass validation.",
                    details={"errors": jsonable_encoder(exc.errors())},
                    request_id=_request_id_from(request),
                )
            ).model_dump(mode="json"),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="HTTP_ERROR",
                    message=str(exc.detail),
                    request_id=_request_id_from(request),
                )
            ).model_dump(mode="json"),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id_from(request)
        logger.exception("Unhandled exception (request_id=%s)", request_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An unexpected error occurred.",
                    request_id=request_id,
                )
            ).model_dump(mode="json"),
        )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(log_level=settings.LOG_LEVEL, environment=settings.ENVIRONMENT)

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Educational/research backend foundation for a future oncology AI platform.\n\n"
            f"**{MEDICAL_DISCLAIMER}**"
        ),
        openapi_tags=[
            {"name": "root", "description": "Service info."},
            {"name": "health", "description": "Liveness/readiness probes."},
            {"name": "auth", "description": "Registration, login, refresh, logout."},
            {"name": "users", "description": "The authenticated user's own profile."},
            {
                "name": "predictions",
                "description": "Prediction history and placeholder inference endpoints.",
            },
        ],
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(RequestIdMiddleware)

    if settings.ALLOWED_HOSTS:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)

    app.include_router(api_router)

    @app.get("/", tags=["root"], summary="API root / service info")
    async def root() -> dict[str, str]:
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "docs_url": "/docs",
            "disclaimer": MEDICAL_DISCLAIMER,
        }

    return app


app = create_app()

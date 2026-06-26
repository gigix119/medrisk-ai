"""Shared FastAPI dependencies: settings, DB session, current user, client info."""

import asyncio
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthorizationError, ModelNotConfiguredError, ModelUnavailableError
from app.db.session import get_db_session
from app.models.user import User
from app.services.auth import get_authenticated_user
from app.services.model_deployment import ActiveHistopathologyModel

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]

_settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{_settings.API_V1_PREFIX.lstrip('/')}/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: DbSessionDep,
    settings: SettingsDep,
) -> User:
    return await get_authenticated_user(session, settings, access_token=token)


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_current_superuser(current_user: CurrentUserDep) -> User:
    """Gate for admin-only actions (registry mutation, audit/evaluation creation - see the
    Phase 8 public/authenticated/admin boundary in docs/THREAT_MODEL.md). `is_superuser`
    already existed on `User` (Phase 1) but was never enforced by any endpoint until now."""
    if not current_user.is_superuser:
        raise AuthorizationError("This action requires an administrator account.")
    return current_user


CurrentSuperuserDep = Annotated[User, Depends(get_current_superuser)]


def get_client_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def get_client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


ClientUserAgentDep = Annotated[str | None, Depends(get_client_user_agent)]
ClientIpDep = Annotated[str | None, Depends(get_client_ip)]


def get_active_histopathology_model(request: Request) -> ActiveHistopathologyModel:
    """Raises a 503 when no model is configured at all, or when one is configured but not
    currently ready (still failed/loading) - never returns a stale or partially-built runtime.
    """
    active: ActiveHistopathologyModel | None = getattr(
        request.app.state, "histopathology_model", None
    )
    if active is None:
        if get_settings().MODEL_BUNDLE_PATH:
            raise ModelUnavailableError()
        raise ModelNotConfiguredError()
    if not active.runtime.health().ready:
        raise ModelUnavailableError()
    return active


def get_inference_semaphore(request: Request) -> asyncio.Semaphore:
    semaphore: asyncio.Semaphore = request.app.state.inference_semaphore
    return semaphore


ActiveHistopathologyModelDep = Annotated[
    ActiveHistopathologyModel, Depends(get_active_histopathology_model)
]
InferenceSemaphoreDep = Annotated[asyncio.Semaphore, Depends(get_inference_semaphore)]

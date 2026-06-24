"""Shared FastAPI dependencies: settings, DB session, current user, client info."""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models.user import User
from app.services.auth import get_authenticated_user

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


def get_client_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def get_client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


ClientUserAgentDep = Annotated[str | None, Depends(get_client_user_agent)]
ClientIpDep = Annotated[str | None, Depends(get_client_ip)]

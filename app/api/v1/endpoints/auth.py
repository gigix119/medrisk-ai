"""Authentication endpoints: register, login, refresh, logout."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import ClientIpDep, ClientUserAgentDep, DbSessionDep, SettingsDep
from app.schemas.auth import LogoutRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserRead
from app.services import auth as auth_service

router = APIRouter()


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(payload: RegisterRequest, session: DbSessionDep) -> UserRead:
    user = await auth_service.register_user(
        session,
        email=payload.email,
        password=payload.password.get_secret_value(),
        full_name=payload.full_name,
    )
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse, summary="Log in and receive a token pair")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: DbSessionDep,
    settings: SettingsDep,
    user_agent: ClientUserAgentDep,
    ip_address: ClientIpDep,
) -> TokenResponse:
    token_pair = await auth_service.login(
        session,
        settings,
        email=form_data.username,
        password=form_data.password,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in,
    )


@router.post("/refresh", response_model=TokenResponse, summary="Rotate a refresh token")
async def refresh(
    payload: RefreshRequest,
    session: DbSessionDep,
    settings: SettingsDep,
    user_agent: ClientUserAgentDep,
    ip_address: ClientIpDep,
) -> TokenResponse:
    token_pair = await auth_service.rotate_refresh_token(
        session,
        settings,
        raw_refresh_token=payload.refresh_token,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a refresh token session",
)
async def logout(payload: LogoutRequest, session: DbSessionDep, settings: SettingsDep) -> None:
    await auth_service.logout(session, settings, raw_refresh_token=payload.refresh_token)

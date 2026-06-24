"""Endpoints for the authenticated user's own profile."""

from fastapi import APIRouter

from app.api.dependencies import CurrentUserDep
from app.schemas.user import UserRead

router = APIRouter()


@router.get("/me", response_model=UserRead, summary="Get the current user's profile")
async def read_current_user(current_user: CurrentUserDep) -> UserRead:
    return UserRead.model_validate(current_user)

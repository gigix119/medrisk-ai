"""Aggregates all /api/v1 endpoint routers."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, predictions, users

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(users.router, prefix="/users", tags=["users"])
api_v1_router.include_router(predictions.router, prefix="/predictions", tags=["predictions"])

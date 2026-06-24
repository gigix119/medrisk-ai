"""Top-level API router: un-versioned health endpoints + the versioned /api/v1 API."""

from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.api.v1.router import api_v1_router
from app.core.config import get_settings

router = APIRouter()
router.include_router(health.router)
router.include_router(api_v1_router, prefix=get_settings().API_V1_PREFIX)

"""Prediction request/response schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import MEDICAL_DISCLAIMER
from app.models.prediction import PredictionModule, PredictionStatus


class PredictionRequest(BaseModel):
    """Placeholder input. Real input schemas (e.g. image upload metadata) arrive in a later phase."""

    notes: str | None = Field(default=None, max_length=1000)


class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    module: PredictionModule
    status: PredictionStatus
    input_metadata: dict[str, Any] | None
    result: dict[str, Any] | None
    confidence_score: float | None
    model_name: str | None
    model_version: str | None
    inference_time_ms: int | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class PredictionNotAvailableResponse(BaseModel):
    """Honest 501 payload returned while no real model is loaded."""

    status: str = "not_implemented"
    module: PredictionModule
    message: str
    disclaimer: str = MEDICAL_DISCLAIMER

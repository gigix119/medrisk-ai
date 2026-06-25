"""Prediction request/response schemas.

`PredictionRead` (used by history + the detail endpoint) is flat and DB-shaped, and never
includes the Grad-CAM image. `HistopathologyPredictionResponse` (the immediate POST result)
is the one place a request gets the richer, nested shape - including the explanation image,
when requested - because it is never persisted or replayed from the database.
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import MEDICAL_DISCLAIMER
from app.models.prediction import PredictionModule, PredictionStatus

DecisionName = Literal["negative", "positive", "review_required"]
ExplanationStatus = Literal["available", "failed", "disabled", "not_requested"]


class PredictionRequest(BaseModel):
    """Placeholder input for the (still-unimplemented) survival module."""

    notes: str | None = Field(default=None, max_length=1000)


class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    module: PredictionModule
    status: PredictionStatus
    request_id: str | None
    client_reference: str | None

    input_sha256: str | None
    input_filename_safe: str | None
    input_format: str | None
    input_size_bytes: int | None
    input_width: int | None
    input_height: int | None
    processed_width: int | None
    processed_height: int | None

    model_id: str | None
    model_name: str | None
    model_version: str | None

    raw_probability: float | None
    calibrated_probability: float | None
    confidence_score: float | None
    predicted_class: str | None
    decision: str | None
    threshold: float | None
    review_lower_bound: float | None
    review_upper_bound: float | None

    preprocessing_time_ms: float | None
    inference_time_ms: int | None
    calibration_time_ms: float | None
    explanation_time_ms: float | None
    total_time_ms: float | None
    explanation_requested: bool
    explanation_status: str | None

    error_code: str | None
    safe_error_message: str | None

    dataset_id: uuid.UUID | None
    dataset_sample_id: uuid.UUID | None
    split: str | None
    ground_truth_label: str | None
    is_correct: bool | None

    input_metadata: dict[str, Any] | None
    result: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class PredictionNotAvailableResponse(BaseModel):
    """Honest 501 payload returned while no real model is loaded (survival module only)."""

    status: str = "not_implemented"
    module: PredictionModule
    message: str
    disclaimer: str = MEDICAL_DISCLAIMER


# --- Histopathology prediction (POST) response: richer, nested, never persisted as-is ---


class InputInfoSchema(BaseModel):
    sha256: str
    format: str
    mime_type: str | None
    size_bytes: int
    original_width: int
    original_height: int
    processed_width: int
    processed_height: int


class ModelInfoSchema(BaseModel):
    model_id: str
    model_name: str
    version: str
    architecture: str
    synthetic_only: bool
    eligible_for_demo: bool


class ReviewPolicySchema(BaseModel):
    negative_probability_max: float
    positive_probability_min: float


class TimingsSchema(BaseModel):
    validation_ms: float
    preprocessing_ms: float
    inference_ms: float
    calibration_ms: float
    explanation_ms: float | None
    total_ms: float


class ExplanationSchema(BaseModel):
    status: ExplanationStatus
    method: str | None = None
    target_layer: str | None = None
    mime_type: str | None = None
    encoding: str | None = None
    data: str | None = None
    width: int | None = None
    height: int | None = None
    generation_time_ms: float | None = None
    error_code: str | None = None
    disclaimer: str | None = None


class HistopathologyPredictionResponse(BaseModel):
    prediction_id: uuid.UUID
    module: Literal[PredictionModule.HISTOPATHOLOGY] = PredictionModule.HISTOPATHOLOGY
    status: PredictionStatus
    decision: DecisionName
    predicted_class: str
    raw_probability: float
    calibrated_probability: float
    predicted_class_probability: float
    confidence_score: float
    positive_class: str
    threshold: float
    review_policy: ReviewPolicySchema | None
    input: InputInfoSchema
    model: ModelInfoSchema
    timings: TimingsSchema
    explanation: ExplanationSchema
    created_at: datetime
    disclaimer: str = MEDICAL_DISCLAIMER

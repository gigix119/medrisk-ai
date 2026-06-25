"""Schemas for the active-model metadata endpoint. Never includes the bundle filesystem
path or any other internal administration detail."""

from datetime import datetime

from pydantic import BaseModel

from app.core.constants import MEDICAL_DISCLAIMER


class InputContractSchema(BaseModel):
    input_height: int
    input_width: int
    input_channels: int


class ReviewPolicySchema(BaseModel):
    negative_probability_max: float
    positive_probability_min: float


class ModelHealthInfo(BaseModel):
    model_id: str
    version: str
    architecture: str
    synthetic_only: bool
    device_type: str
    warmup_completed: bool


class ModelHealthResponse(BaseModel):
    status: str
    model: ModelHealthInfo | None = None


class ActiveModelResponse(BaseModel):
    module: str
    model_id: str
    model_name: str
    version: str
    architecture: str
    dataset_name: str
    dataset_mode: str
    synthetic_only: bool
    eligible_for_demo: bool
    input_contract: InputContractSchema
    class_names: tuple[str, str]
    positive_class: str
    threshold: float
    review_policy: ReviewPolicySchema | None
    calibration_enabled: bool
    activated_at: datetime | None
    disclaimer: str = MEDICAL_DISCLAIMER

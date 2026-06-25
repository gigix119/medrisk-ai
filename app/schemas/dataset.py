"""Dataset registry request/response schemas (Phase 6).

`DatasetSampleRead` deliberately omits `relative_path` - the on-disk location is never
returned by any API response (same principle as `ModelDeployment.bundle_path`); clients only
ever get an `image_url` pointing at the dedicated, access-controlled image endpoint.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import MEDICAL_DISCLAIMER
from app.schemas.prediction import (
    ExplanationSchema,
    InputInfoSchema,
    ModelInfoSchema,
    ReviewPolicySchema,
    TimingsSchema,
)


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    version: str
    description: str
    source_name: str
    source_url: str | None
    license_name: str
    license_url: str | None
    citation: str | None
    intended_use: str
    prohibited_use: str
    modality: str
    task_type: str
    classes: list[str]
    sample_count: int
    image_width: int
    image_height: int
    image_channels: int
    split_names: list[str]
    class_distribution: dict
    preprocessing_summary: str | None
    known_limitations: str
    ethical_notes: str
    is_synthetic: bool
    is_public: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DatasetSampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    sample_key: str
    split: str
    filename: str
    ground_truth_label: str
    class_index: int
    width: int
    height: int
    mime_type: str
    checksum_sha256: str
    source_reference: str | None
    license_reference: str | None
    is_synthetic: bool
    notes: str | None
    image_url: str = Field(
        description="Relative URL to GET the sample image; built by the endpoint, not a DB column."
    )


class PredictOnSampleRequest(BaseModel):
    include_explanation: bool = False
    client_reference: str | None = Field(default=None, max_length=100)


class PredictOnSampleResponse(BaseModel):
    prediction_id: uuid.UUID
    dataset_id: uuid.UUID
    dataset_sample_id: uuid.UUID
    dataset_name: str
    dataset_slug: str
    dataset_version: str
    sample_key: str
    split: str
    ground_truth_label: str
    predicted_class: str
    is_correct: bool
    decision: str
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
    warnings: list[str] = Field(default_factory=list)
    research_disclaimer: str = MEDICAL_DISCLAIMER

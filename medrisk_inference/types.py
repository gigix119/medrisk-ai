"""Typed internal result objects passed between inference stages.

These are plain dataclasses, not Pydantic models: they never cross a process boundary on
their own (the FastAPI layer maps them into app/schemas response models at the edge), so
there is no need for JSON validation here - only for clear, typed internal contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DecisionLiteral = Literal["negative", "positive", "review_required"]


@dataclass(frozen=True)
class ReviewPolicy:
    negative_probability_max: float
    positive_probability_min: float


@dataclass(frozen=True)
class ValidatedImage:
    rgb_image_bytes: bytes  # raw RGB pixel buffer (image.tobytes()), not a re-encoded file
    width: int
    height: int
    mode: str
    declared_format: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class PreprocessedInput:
    tensor_shape: tuple[int, int, int, int]
    processed_width: int
    processed_height: int


@dataclass(frozen=True)
class RawModelOutput:
    logit: float
    raw_probability: float


@dataclass(frozen=True)
class DecisionResult:
    calibrated_probability: float
    predicted_class: str
    predicted_class_probability: float
    confidence_score: float
    decision: DecisionLiteral
    threshold: float
    review_policy: ReviewPolicy | None


@dataclass(frozen=True)
class ExplanationResult:
    status: Literal["available", "failed", "disabled", "not_requested"]
    method: str = "grad_cam"
    target_layer: str | None = None
    mime_type: str | None = None
    encoding: str | None = None
    data: str | None = None
    width: int | None = None
    height: int | None = None
    generation_time_ms: float | None = None
    error_code: str | None = None
    disclaimer: str | None = None


@dataclass(frozen=True)
class InferenceTimings:
    validation_ms: float = 0.0
    preprocessing_ms: float = 0.0
    inference_ms: float = 0.0
    calibration_ms: float = 0.0
    explanation_ms: float | None = None
    total_ms: float = 0.0


@dataclass(frozen=True)
class ModelIdentity:
    model_id: str
    model_name: str
    model_version: str
    architecture: str
    dataset_name: str
    dataset_mode: str
    synthetic_only: bool
    eligible_for_demo: bool
    bundle_sha256: str
    class_names: tuple[str, str]
    positive_class: str
    input_height: int
    input_width: int
    input_channels: int


@dataclass(frozen=True)
class InferenceResult:
    model: ModelIdentity
    validated_image: ValidatedImage
    processed: PreprocessedInput
    raw_output: RawModelOutput
    decision: DecisionResult
    explanation: ExplanationResult
    timings: InferenceTimings


@dataclass(frozen=True)
class RuntimeHealth:
    configured: bool
    bundle_verified: bool
    model_loaded: bool
    warmup_completed: bool
    ready: bool
    device: str
    model_id: str | None
    model_version: str | None
    synthetic_only: bool | None
    last_error_code: str | None = None
    extra: dict[str, object] = field(default_factory=dict)

"""Top-level orchestration, split into two stages so callers that must create a database
audit row *between* validating an upload and running the model (see
docs/inference-architecture.md "Database transaction flow") can do so without duplicating
validation logic:

1. `validate_upload` - decode/validate the image bytes only.
2. `run_validated_inference` - predict (+ optional explain) against an already-validated image.

`run_inference` composes both in one call for callers that don't need a step in between
(the CLI's `predict`/`benchmark` commands).
"""

from __future__ import annotations

import time

from medrisk_inference.exceptions import ImageDimensionsInvalidError
from medrisk_inference.image_validation import validate_image_bytes
from medrisk_inference.runtime import HistopathologyModelRuntime
from medrisk_inference.types import (
    ExplanationResult,
    InferenceResult,
    InferenceTimings,
    ModelIdentity,
    ValidatedImage,
)


def validate_upload(
    runtime: HistopathologyModelRuntime,
    image_bytes: bytes,
    *,
    declared_content_type: str | None = None,
) -> tuple[ValidatedImage, float]:
    """Returns the validated image plus how long validation took, in milliseconds.

    When `STRICT_MODEL_INPUT_SHAPE=true` (the default), the image must already match the
    bundle's exact input dimensions - this is a patch-classification model, not a
    whole-slide-image resizer, and silently resizing an arbitrary upload into the model's
    input shape would invite a distribution shift the model was never evaluated against.
    """
    started = time.perf_counter()
    validated_image = validate_image_bytes(
        image_bytes, config=runtime.config, declared_content_type=declared_content_type
    )
    if runtime.config.strict_model_input_shape:
        manifest = runtime.manifest
        if (
            validated_image.width != manifest.input_width
            or validated_image.height != manifest.input_height
        ):
            raise ImageDimensionsInvalidError(
                f"Image dimensions {validated_image.width}x{validated_image.height} do not "
                f"match the required {manifest.input_width}x{manifest.input_height} input "
                "shape. This endpoint accepts patches matching the model's input contract, "
                "not arbitrary whole-slide images."
            )
    return validated_image, (time.perf_counter() - started) * 1000


def run_validated_inference(
    runtime: HistopathologyModelRuntime,
    validated_image: ValidatedImage,
    *,
    validation_ms: float = 0.0,
    include_explanation: bool = False,
) -> InferenceResult:
    overall_started = time.perf_counter()
    outcome = runtime.predict(validated_image)

    explanation: ExplanationResult
    if include_explanation:
        explanation = runtime.explain(outcome, validated_image)
    else:
        explanation = ExplanationResult(status="not_requested")

    total_ms = validation_ms + (time.perf_counter() - overall_started) * 1000
    manifest = runtime.manifest
    return InferenceResult(
        model=ModelIdentity(
            model_id=manifest.model_id,
            model_name=manifest.model_name,
            model_version=manifest.model_version,
            architecture=manifest.architecture,
            dataset_name=manifest.dataset_name,
            dataset_mode=manifest.dataset_mode,
            synthetic_only=manifest.synthetic_only,
            eligible_for_demo=manifest.eligible_for_demo,
            bundle_sha256=runtime.bundle_sha256,
            class_names=manifest.class_names,
            positive_class=manifest.positive_class,
            input_height=manifest.input_height,
            input_width=manifest.input_width,
            input_channels=manifest.input_channels,
        ),
        validated_image=validated_image,
        processed=outcome.processed,
        raw_output=outcome.raw_output,
        decision=outcome.decision,
        explanation=explanation,
        timings=InferenceTimings(
            validation_ms=validation_ms,
            preprocessing_ms=outcome.timings.preprocessing_ms,
            inference_ms=outcome.timings.inference_ms,
            calibration_ms=outcome.timings.calibration_ms,
            explanation_ms=explanation.generation_time_ms,
            total_ms=total_ms,
        ),
    )


def run_inference(
    runtime: HistopathologyModelRuntime,
    image_bytes: bytes,
    *,
    declared_content_type: str | None = None,
    include_explanation: bool = False,
) -> InferenceResult:
    """Convenience wrapper for callers with no need for a step between validation and
    prediction (the CLI). The FastAPI service layer uses `validate_upload` +
    `run_validated_inference` directly so it can create the pending DB row in between.
    """
    validated_image, validation_ms = validate_upload(
        runtime, image_bytes, declared_content_type=declared_content_type
    )
    return run_validated_inference(
        runtime,
        validated_image,
        validation_ms=validation_ms,
        include_explanation=include_explanation,
    )

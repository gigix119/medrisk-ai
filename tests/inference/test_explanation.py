"""Unit tests for medrisk_inference.explanation (Grad-CAM)."""

from __future__ import annotations

import base64
import io

import numpy as np
import pytest
from PIL import Image

from medrisk_inference.exceptions import ExplanationNotSupportedError
from medrisk_inference.explanation import generate_explanation
from medrisk_inference.image_validation import validate_image_bytes
from medrisk_inference.runtime import HistopathologyModelRuntime


def _png_bytes(size: int) -> bytes:
    pixels = np.random.default_rng(9).integers(0, 256, size=(size, size, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def test_explanation_is_generated(runtime: HistopathologyModelRuntime) -> None:
    validated = validate_image_bytes(_png_bytes(32), config=runtime.config)
    outcome = runtime.predict(validated)
    explanation = runtime.explain(outcome, validated)

    assert explanation.status == "available"
    assert explanation.method == "grad_cam"
    assert explanation.mime_type == "image/png"
    assert explanation.encoding == "base64"
    assert explanation.disclaimer is not None
    assert "not a biological explanation" in explanation.disclaimer


def test_explanation_data_decodes_to_valid_png(runtime: HistopathologyModelRuntime) -> None:
    validated = validate_image_bytes(_png_bytes(32), config=runtime.config)
    outcome = runtime.predict(validated)
    explanation = runtime.explain(outcome, validated)

    assert explanation.data is not None
    raw_png = base64.b64decode(explanation.data)
    decoded = Image.open(io.BytesIO(raw_png))
    decoded.verify()


def test_explanation_dimensions_match_processed_size(runtime: HistopathologyModelRuntime) -> None:
    validated = validate_image_bytes(_png_bytes(32), config=runtime.config)
    outcome = runtime.predict(validated)
    explanation = runtime.explain(outcome, validated)

    assert explanation.width == outcome.processed.processed_width
    assert explanation.height == outcome.processed.processed_height


def test_explanation_respects_max_output_bytes(runtime: HistopathologyModelRuntime) -> None:
    runtime.config = type(runtime.config)(**{**vars(runtime.config), "gradcam_max_output_bytes": 1})
    validated = validate_image_bytes(_png_bytes(32), config=runtime.config)
    outcome = runtime.predict(validated)
    explanation = runtime.explain(outcome, validated)

    assert explanation.status == "failed"
    assert explanation.error_code == "EXPLANATION_FAILED"


def test_explanation_disabled_returns_disabled_status(runtime: HistopathologyModelRuntime) -> None:
    runtime.config = type(runtime.config)(**{**vars(runtime.config), "gradcam_enabled": False})
    validated = validate_image_bytes(_png_bytes(32), config=runtime.config)
    outcome = runtime.predict(validated)
    explanation = runtime.explain(outcome, validated)

    assert explanation.status == "disabled"


def test_hooks_removed_after_generation_does_not_leak(runtime: HistopathologyModelRuntime) -> None:
    validated = validate_image_bytes(_png_bytes(32), config=runtime.config)
    for _ in range(3):
        outcome = runtime.predict(validated)
        runtime.explain(outcome, validated)
    # No hook accumulation: a fresh GradCAM/ActivationsAndGradients is created and released
    # per call (see explanation.py), so the target layer should have no forward hooks left
    # registered between calls.
    target_layer = runtime.model.features[-1]
    assert len(target_layer._forward_hooks) == 0


def test_explanation_failure_does_not_corrupt_model_state(
    runtime: HistopathologyModelRuntime,
) -> None:
    validated = validate_image_bytes(_png_bytes(32), config=runtime.config)

    runtime.config = type(runtime.config)(**{**vars(runtime.config), "gradcam_max_output_bytes": 1})
    outcome = runtime.predict(validated)
    failed_explanation = runtime.explain(outcome, validated)
    assert failed_explanation.status == "failed"

    runtime.config = type(runtime.config)(
        **{**vars(runtime.config), "gradcam_max_output_bytes": 500_000}
    )
    outcome_again = runtime.predict(validated)
    assert outcome_again.decision.calibrated_probability == pytest.approx(
        outcome.decision.calibrated_probability
    )
    explanation_again = runtime.explain(outcome_again, validated)
    assert explanation_again.status == "available"


def test_unsupported_architecture_is_reported_cleanly(runtime: HistopathologyModelRuntime) -> None:
    validated = validate_image_bytes(_png_bytes(32), config=runtime.config)
    outcome = runtime.predict(validated)
    base_image = Image.frombytes(
        validated.mode, (validated.width, validated.height), validated.rgb_image_bytes
    )
    with pytest.raises(ExplanationNotSupportedError):
        generate_explanation(
            runtime.model,
            "not_a_real_architecture",
            outcome.tensor,
            base_image,
            max_output_bytes=500_000,
        )

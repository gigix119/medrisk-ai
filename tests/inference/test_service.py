"""Unit tests for medrisk_inference.service (validate_upload / run_validated_inference /
run_inference orchestration)."""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from medrisk_inference.exceptions import ImageDimensionsInvalidError
from medrisk_inference.runtime import HistopathologyModelRuntime
from medrisk_inference.service import run_inference, run_validated_inference, validate_upload


def _png_bytes(size: int) -> bytes:
    pixels = np.random.default_rng(3).integers(0, 256, size=(size, size, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def test_validate_upload_accepts_matching_dimensions(runtime: HistopathologyModelRuntime) -> None:
    validated_image, validation_ms = validate_upload(runtime, _png_bytes(32))
    assert validated_image.width == 32
    assert validated_image.height == 32
    assert validation_ms >= 0.0


def test_validate_upload_rejects_mismatched_dimensions_in_strict_mode(
    runtime: HistopathologyModelRuntime,
) -> None:
    assert runtime.config.strict_model_input_shape is True
    with pytest.raises(ImageDimensionsInvalidError):
        validate_upload(runtime, _png_bytes(64))


def test_validate_upload_allows_mismatched_dimensions_when_strict_mode_disabled(
    runtime: HistopathologyModelRuntime,
) -> None:
    runtime.config = type(runtime.config)(
        **{
            **vars(runtime.config),
            "strict_model_input_shape": False,
            "max_image_width": 4096,
            "max_image_height": 4096,
        }
    )
    validated_image, _ = validate_upload(runtime, _png_bytes(64))
    assert validated_image.width == 64


def test_run_inference_end_to_end(runtime: HistopathologyModelRuntime) -> None:
    result = run_inference(runtime, _png_bytes(32), include_explanation=False)
    assert result.explanation.status == "not_requested"
    assert result.timings.total_ms >= 0.0
    assert result.model.model_id == runtime.manifest.model_id


def test_run_validated_inference_with_explanation(runtime: HistopathologyModelRuntime) -> None:
    validated_image, validation_ms = validate_upload(runtime, _png_bytes(32))
    result = run_validated_inference(
        runtime, validated_image, validation_ms=validation_ms, include_explanation=True
    )
    assert result.explanation.status == "available"
    assert result.timings.explanation_ms is not None
    assert result.timings.validation_ms == pytest.approx(validation_ms)

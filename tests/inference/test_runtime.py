"""Unit tests for medrisk_inference.runtime.HistopathologyModelRuntime."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from medrisk_inference.config import InferenceConfig
from medrisk_inference.exceptions import BundleInvalidError, ModelNotReadyError, ModelWarmupError
from medrisk_inference.image_validation import validate_image_bytes
from medrisk_inference.runtime import HistopathologyModelRuntime


def _png_bytes(size: int) -> bytes:
    pixels = np.random.default_rng(5).integers(0, 256, size=(size, size, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def test_runtime_loads_and_is_ready(runtime: HistopathologyModelRuntime) -> None:
    health = runtime.health()
    assert health.model_loaded is True
    assert health.ready is True
    assert health.warmup_completed is True


def test_predict_produces_valid_result(runtime: HistopathologyModelRuntime) -> None:
    validated = validate_image_bytes(_png_bytes(32), config=runtime.config)
    outcome = runtime.predict(validated)

    assert 0.0 <= outcome.raw_output.raw_probability <= 1.0
    assert 0.0 <= outcome.decision.calibrated_probability <= 1.0
    assert outcome.decision.predicted_class in ("negative", "positive")
    assert outcome.decision.decision in ("negative", "positive", "review_required")
    assert outcome.timings.inference_ms >= 0.0


def test_predict_uses_inference_mode_not_grad(runtime: HistopathologyModelRuntime) -> None:
    validated = validate_image_bytes(_png_bytes(32), config=runtime.config)
    outcome = runtime.predict(validated)
    assert outcome.tensor.requires_grad is False


def test_predict_before_ready_raises(bundle_dir: Path) -> None:
    config = InferenceConfig(
        environment="test", model_bundle_path=str(bundle_dir), model_warmup_enabled=False
    )
    runtime = HistopathologyModelRuntime.load(str(bundle_dir), config)
    runtime._ready = False  # simulate a not-yet-ready runtime

    validated = validate_image_bytes(_png_bytes(32), config=config)
    with pytest.raises(ModelNotReadyError):
        runtime.predict(validated)


def test_warmup_disabled_still_marks_ready_without_running_warmup(bundle_dir: Path) -> None:
    config = InferenceConfig(
        environment="test", model_bundle_path=str(bundle_dir), model_warmup_enabled=False
    )
    runtime = HistopathologyModelRuntime.load(str(bundle_dir), config)
    health = runtime.health()
    assert health.ready is True
    assert health.warmup_completed is False


def test_failed_warmup_prevents_readiness(runtime: HistopathologyModelRuntime) -> None:
    # Corrupt the loaded model in a way that breaks the forward pass, then re-run warmup
    # directly to confirm failure correctly flips readiness off.
    broken_layer = runtime.model.classifier[-1]
    original_forward = broken_layer.forward

    def _broken_forward(*_args: object, **_kwargs: object) -> torch.Tensor:
        return torch.full((1, 1), float("nan"))

    broken_layer.forward = _broken_forward  # type: ignore[method-assign]
    try:
        with pytest.raises(ModelWarmupError):
            runtime.warmup()
    finally:
        broken_layer.forward = original_forward  # type: ignore[method-assign]

    assert runtime.health().ready is False


def test_runtime_health_reports_synthetic_status(runtime: HistopathologyModelRuntime) -> None:
    assert runtime.health().synthetic_only is True


def test_close_marks_not_ready(runtime: HistopathologyModelRuntime) -> None:
    runtime.close()
    assert runtime.health().ready is False


def test_load_rejects_invalid_bundle(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty-bundle"
    empty_dir.mkdir()
    config = InferenceConfig(environment="test", model_bundle_path=str(empty_dir))
    with pytest.raises(BundleInvalidError):
        HistopathologyModelRuntime.load(str(empty_dir), config)

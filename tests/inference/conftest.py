"""Shared fixtures for medrisk_inference unit tests."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from medrisk_inference.config import InferenceConfig
from medrisk_inference.runtime import HistopathologyModelRuntime
from tests.inference.fixtures.builder import build_constant_output_bundle

TEST_IMAGE_SIZE = 32


@pytest.fixture
def bundle_dir(tmp_path: Path) -> Path:
    """A verified, synthetic, constant-output (threshold=0.5, no review band) bundle."""
    return build_constant_output_bundle(tmp_path, image_size=TEST_IMAGE_SIZE)


@pytest.fixture
def review_bundle_dir(tmp_path: Path) -> Path:
    """Same constant-output model, but with a review band that brackets its fixed 0.5
    output - deterministically exercises the `review_required` decision path."""
    return build_constant_output_bundle(
        tmp_path,
        model_name="test-review-cnn",
        image_size=TEST_IMAGE_SIZE,
        threshold=0.5,
        review_policy={"negative_probability_max": 0.3, "positive_probability_min": 0.7},
    )


def _inference_config(bundle_path: Path, **overrides: object) -> InferenceConfig:
    base = {
        "environment": "test",
        "model_bundle_path": str(bundle_path),
        "model_device": "cpu",
        "model_warmup_enabled": True,
    }
    base.update(overrides)
    return InferenceConfig(**base)  # type: ignore[arg-type]


@pytest.fixture
def inference_config(bundle_dir: Path) -> InferenceConfig:
    return _inference_config(bundle_dir)


@pytest.fixture
def runtime(bundle_dir: Path) -> HistopathologyModelRuntime:
    return HistopathologyModelRuntime.load(str(bundle_dir), _inference_config(bundle_dir))


@pytest.fixture
def review_runtime(review_bundle_dir: Path) -> HistopathologyModelRuntime:
    return HistopathologyModelRuntime.load(
        str(review_bundle_dir), _inference_config(review_bundle_dir)
    )


def _encode_image(*, size: tuple[int, int], fmt: str) -> bytes:
    rng = np.random.default_rng(seed=42)
    pixels = rng.integers(0, 256, size=(size[1], size[0], 3), dtype=np.uint8)
    image = Image.fromarray(pixels, mode="RGB")
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture
def sample_png_bytes() -> bytes:
    return _encode_image(size=(TEST_IMAGE_SIZE, TEST_IMAGE_SIZE), fmt="PNG")


@pytest.fixture
def sample_jpeg_bytes() -> bytes:
    return _encode_image(size=(TEST_IMAGE_SIZE, TEST_IMAGE_SIZE), fmt="JPEG")

"""Unit tests for medrisk_inference.preprocessing, including the critical parity test
against the exact Phase 2 evaluation transform.
"""

from __future__ import annotations

import io

import numpy as np
import torch
from PIL import Image

from medrisk_inference.config import InferenceConfig
from medrisk_inference.image_validation import validate_image_bytes
from medrisk_inference.preprocessing import build_inference_transform, preprocess
from medrisk_ml.data.transforms import build_transform
from medrisk_ml.registry.manifest import ModelManifest

IMAGE_SIZE = 32
NORMALIZATION = {"mean": [0.5, 0.4, 0.3], "std": [0.2, 0.2, 0.2]}


def _manifest(architecture: str = "baseline_cnn") -> ModelManifest:
    return ModelManifest(
        model_id="parity-test:0.0.1",
        model_name="parity-test",
        model_version="0.0.1",
        architecture=architecture,
        checkpoint_sha256="0" * 64,
        dataset_name="synthetic",
        dataset_version="synthetic-v1",
        dataset_mode="synthetic",
        input_height=IMAGE_SIZE,
        input_width=IMAGE_SIZE,
        input_channels=3,
        class_names=("negative", "positive"),
        positive_class="positive",
        normalization=NORMALIZATION,
        threshold=0.5,
        review_policy=None,
        calibration=None,
        validation_metrics={},
        test_metrics=None,
        git_commit=None,
        created_at="2026-01-01T00:00:00+00:00",
        eligible_for_demo=False,
        synthetic_only=True,
    )


def _sample_image() -> Image.Image:
    pixels = np.random.default_rng(7).integers(0, 256, size=(48, 40, 3), dtype=np.uint8)
    return Image.fromarray(pixels, mode="RGB")


def test_inference_transform_matches_phase2_eval_transform_baseline_cnn() -> None:
    manifest = _manifest("baseline_cnn")
    image = _sample_image()

    inference_transform = build_inference_transform(manifest)
    eval_transform = build_transform(
        "test",
        "baseline_cnn",
        image_size=IMAGE_SIZE,
        mean=tuple(NORMALIZATION["mean"]),
        std=tuple(NORMALIZATION["std"]),
    )

    inference_tensor = inference_transform(image)
    eval_tensor = eval_transform(image)

    assert inference_tensor.shape == eval_tensor.shape
    assert torch.allclose(inference_tensor, eval_tensor)


def test_inference_transform_matches_phase2_eval_transform_resnet18() -> None:
    manifest = _manifest("resnet18")
    image = _sample_image()

    inference_transform = build_inference_transform(manifest)
    eval_transform = build_transform("test", "resnet18", image_size=IMAGE_SIZE)

    inference_tensor = inference_transform(image)
    eval_tensor = eval_transform(image)

    assert torch.allclose(inference_tensor, eval_tensor)


def test_preprocess_output_shape_and_dtype() -> None:
    manifest = _manifest()
    transform = build_inference_transform(manifest)

    buffer = io.BytesIO()
    _sample_image().save(buffer, format="PNG")
    validated = validate_image_bytes(buffer.getvalue(), config=InferenceConfig(environment="test"))

    tensor, processed = preprocess(validated, transform)
    assert tensor.shape == (1, 3, IMAGE_SIZE, IMAGE_SIZE)
    assert tensor.dtype == torch.float32
    assert processed.processed_width == IMAGE_SIZE
    assert processed.processed_height == IMAGE_SIZE


def test_preprocess_is_deterministic() -> None:
    manifest = _manifest()
    transform = build_inference_transform(manifest)

    buffer = io.BytesIO()
    _sample_image().save(buffer, format="PNG")
    validated = validate_image_bytes(buffer.getvalue(), config=InferenceConfig(environment="test"))

    tensor_a, _ = preprocess(validated, transform)
    tensor_b, _ = preprocess(validated, transform)
    assert torch.equal(tensor_a, tensor_b)


def test_no_random_augmentation_in_inference_transform() -> None:
    """The inference transform must be the deterministic eval pipeline, never the
    randomized training augmentation pipeline."""
    manifest = _manifest()
    transform = build_inference_transform(manifest)
    transform_op_names = {type(op).__name__ for op in transform.transforms}
    randomized_ops = {
        "RandomHorizontalFlip",
        "RandomVerticalFlip",
        "RandomAffine",
        "ColorJitter",
        "RandomChoice",
    }
    assert transform_op_names.isdisjoint(randomized_ops)

from __future__ import annotations

import pytest
import torch
from PIL import Image

from medrisk_ml.data.transforms import build_transform

IMAGE_SIZE = 64


def _solid_image(value: int = 120) -> Image.Image:
    return Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), color=(value, value, value))


def test_test_transform_output_shape_and_dtype() -> None:
    transform = build_transform(
        "test", "baseline_cnn", IMAGE_SIZE, mean=(0.5, 0.5, 0.5), std=(0.25, 0.25, 0.25)
    )
    tensor = transform(_solid_image())
    assert tensor.shape == (3, IMAGE_SIZE, IMAGE_SIZE)
    assert tensor.dtype == torch.float32


def test_validation_transform_is_deterministic() -> None:
    transform = build_transform(
        "val", "baseline_cnn", IMAGE_SIZE, mean=(0.5, 0.5, 0.5), std=(0.25, 0.25, 0.25)
    )
    image = _solid_image(77)
    first = transform(image)
    second = transform(image)
    assert torch.equal(first, second)


def test_train_transform_preserves_shape() -> None:
    transform = build_transform(
        "train", "baseline_cnn", IMAGE_SIZE, mean=(0.5, 0.5, 0.5), std=(0.25, 0.25, 0.25)
    )
    tensor = transform(_solid_image())
    assert tensor.shape == (3, IMAGE_SIZE, IMAGE_SIZE)
    assert torch.isfinite(tensor).all()


def test_resnet18_uses_imagenet_normalization_regardless_of_mean_std_args() -> None:
    transform_a = build_transform("test", "resnet18", IMAGE_SIZE, mean=None, std=None)
    transform_b = build_transform(
        "test", "resnet18", IMAGE_SIZE, mean=(0.1, 0.1, 0.1), std=(0.9, 0.9, 0.9)
    )
    image = _solid_image(200)
    assert torch.equal(transform_a(image), transform_b(image))


def test_baseline_cnn_requires_mean_std() -> None:
    with pytest.raises(ValueError, match="mean/std"):
        build_transform("test", "baseline_cnn", IMAGE_SIZE, mean=None, std=None)


def test_value_range_before_normalization() -> None:
    # ToTensor alone (identity normalization) must produce values in [0, 1].
    transform = build_transform(
        "test", "baseline_cnn", IMAGE_SIZE, mean=(0.0, 0.0, 0.0), std=(1.0, 1.0, 1.0)
    )
    tensor = transform(_solid_image(255))
    assert tensor.max().item() <= 1.0
    assert tensor.min().item() >= 0.0


def test_label_preservation_with_dataset() -> None:
    from medrisk_ml.data.synthetic import SyntheticHistopathologyDataset

    transform = build_transform(
        "train", "baseline_cnn", IMAGE_SIZE, mean=(0.5, 0.5, 0.5), std=(0.25, 0.25, 0.25)
    )
    plain_dataset = SyntheticHistopathologyDataset(
        "train", num_samples=4, seed=5, image_size=IMAGE_SIZE
    )
    transformed_dataset = SyntheticHistopathologyDataset(
        "train", num_samples=4, seed=5, image_size=IMAGE_SIZE, transform=transform
    )
    for index in range(4):
        _, plain_label, plain_id = plain_dataset[index]
        _, transformed_label, transformed_id = transformed_dataset[index]
        assert plain_label == transformed_label
        assert plain_id == transformed_id

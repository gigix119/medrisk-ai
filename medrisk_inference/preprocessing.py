"""Inference-time preprocessing: builds and applies *exactly* the deterministic transform
Phase 2 uses for validation/test/inference (`medrisk_ml.data.transforms.build_transform`),
parameterized only from the bundle's own manifest - no hardcoded normalization values are
duplicated here. See tests/inference/test_preprocessing.py for the parity test against the
Phase 2 evaluation transform.
"""

from __future__ import annotations

import torch
from PIL import Image
from torchvision import transforms as T

from medrisk_inference.types import PreprocessedInput, ValidatedImage
from medrisk_ml.data.transforms import build_transform
from medrisk_ml.registry.manifest import ModelManifest


def build_inference_transform(manifest: ModelManifest) -> T.Compose:
    mean = manifest.normalization.get("mean")
    std = manifest.normalization.get("std")
    return build_transform(
        "inference",
        manifest.architecture,  # type: ignore[arg-type]
        image_size=manifest.input_height,
        mean=tuple(mean) if mean is not None else None,
        std=tuple(std) if std is not None else None,
    )


def preprocess(
    validated_image: ValidatedImage, transform: T.Compose
) -> tuple[torch.Tensor, PreprocessedInput]:
    """Build a PIL image from validated pixel bytes (never the original upload object) and
    apply the deterministic inference transform, returning a (1, C, H, W) batch tensor.
    """
    pil_image = Image.frombytes(
        validated_image.mode,
        (validated_image.width, validated_image.height),
        validated_image.rgb_image_bytes,
    )
    tensor = transform(pil_image)
    batch = tensor.unsqueeze(0)
    _, _, height, width = batch.shape
    return batch, PreprocessedInput(
        tensor_shape=tuple(batch.shape),
        processed_width=width,
        processed_height=height,
    )

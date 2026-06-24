"""Deterministic synthetic histopathology-like dataset for tests, CI, and smoke training.

SYNTHETIC DATA - NOT MEDICAL PERFORMANCE. These are simple generated patterns, not real
tissue: class 0 ("negative") is diffuse low-frequency noise, class 1 ("positive") is the
same noise with an added centered bright structured region. The point is only that a
small CNN can learn *something* non-random in a couple of epochs, so the rest of the
pipeline (checkpointing, evaluation, calibration, Grad-CAM, registry, bundle) can be
exercised end to end without downloading real data.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import torch
from PIL import Image, ImageFilter
from torch.utils.data import Dataset
from torchvision import transforms as T

from medrisk_ml.constants import CLASS_NAMES, SYNTHETIC_DATA_WARNING
from medrisk_ml.types import SplitName

_SPLIT_OFFSETS: dict[SplitName, int] = {"train": 0, "val": 1, "test": 2}


def synthetic_disclaimer() -> str:
    return SYNTHETIC_DATA_WARNING


def _generate_image(rng: np.random.Generator, label: int, image_size: int) -> Image.Image:
    noise = rng.normal(loc=128.0, scale=25.0, size=(image_size, image_size, 3))
    base = np.clip(noise, 0, 255).astype(np.uint8)
    image = Image.fromarray(base, mode="RGB").filter(ImageFilter.GaussianBlur(radius=3))
    if label == 1:
        image = _add_central_structure(image, rng, image_size)
    return image


def _add_central_structure(
    image: Image.Image, rng: np.random.Generator, image_size: int
) -> Image.Image:
    array = np.array(image, dtype=np.float64)
    center = image_size / 2.0
    radius = image_size * rng.uniform(0.18, 0.30)
    yy, xx = np.mgrid[0:image_size, 0:image_size]
    distance = np.sqrt((xx - center) ** 2 + (yy - center) ** 2)
    mask = distance <= radius
    intensity = rng.uniform(180.0, 255.0)
    tint = np.array([intensity, intensity * 0.55, intensity * 0.65])
    array[mask] = array[mask] * 0.25 + tint * 0.75
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), mode="RGB")


class SyntheticHistopathologyDataset(Dataset[tuple[torch.Tensor, int, str]]):
    """SYNTHETIC DATA - NOT MEDICAL PERFORMANCE. See module docstring.

    Images are generated lazily but deterministically: the same (seed, split, index)
    always yields the same image, independent of access order or DataLoader workers.
    """

    classes: tuple[str, str] = CLASS_NAMES

    def __init__(
        self,
        split: SplitName,
        num_samples: int,
        seed: int,
        image_size: int = 96,
        transform: Callable[[Image.Image], torch.Tensor] | None = None,
    ) -> None:
        if num_samples <= 0:
            raise ValueError("num_samples must be positive")
        if split not in _SPLIT_OFFSETS:
            raise ValueError(f"Unknown split: {split!r}")
        self.split = split
        self.num_samples = num_samples
        self.seed = seed
        self.image_size = image_size
        self.transform: Callable[[Image.Image], torch.Tensor] = transform or T.ToTensor()

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int, str]:
        if not 0 <= index < self.num_samples:
            raise IndexError(index)
        label = index % 2
        rng = np.random.default_rng([self.seed, _SPLIT_OFFSETS[self.split], index])
        image = _generate_image(rng, label, self.image_size)
        tensor = self.transform(image)
        sample_id = f"synthetic_{self.split}_{index:06d}"
        return tensor, label, sample_id

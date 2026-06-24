"""Train/validation/test/inference transform pipelines.

Validation, test, and inference transforms are always deterministic (Resize -> ToTensor ->
Normalize, no randomness) - required for reproducible evaluation, calibration, and
Grad-CAM. Training transforms add conservative, morphology-preserving augmentation: PCam
patches are tissue crops with no canonical "up," so flips and 90-degree rotations are
label-preserving, but aggressive distortions (large shear, heavy color shifts) are not used
because they could destroy the morphology the model is meant to learn from.
"""

from __future__ import annotations

from typing import Literal

from torchvision import transforms as T
from torchvision.transforms import functional as TF

from medrisk_ml.constants import IMAGENET_MEAN, IMAGENET_STD
from medrisk_ml.types import ArchitectureName, SplitName


def _rotate90_choice() -> T.RandomChoice:
    return T.RandomChoice(
        [T.Lambda(lambda img, angle=angle: TF.rotate(img, angle)) for angle in (0, 90, 180, 270)]
    )


def _normalization_for(
    architecture: ArchitectureName,
    mean: tuple[float, ...] | None,
    std: tuple[float, ...] | None,
) -> T.Normalize:
    if architecture == "resnet18":
        # Pretrained ResNet18 weights were trained with ImageNet preprocessing - this is
        # documented, not computed, because changing it would invalidate the pretrained
        # backbone's learned features.
        return T.Normalize(mean=list(IMAGENET_MEAN), std=list(IMAGENET_STD))
    if mean is None or std is None:
        raise ValueError(
            "baseline_cnn normalization requires train-set mean/std from "
            "data/statistics.py::compute_normalization_stats (never computed from "
            "validation/test data)"
        )
    return T.Normalize(mean=list(mean), std=list(std))


def build_transform(
    split: SplitName | Literal["inference"],
    architecture: ArchitectureName,
    image_size: int = 96,
    mean: tuple[float, ...] | None = None,
    std: tuple[float, ...] | None = None,
) -> T.Compose:
    """Build the transform pipeline for one split (or "inference", same as test/val)."""
    ops: list[object] = [T.Resize((image_size, image_size))]
    if split == "train":
        ops += [
            T.RandomHorizontalFlip(p=0.5),
            T.RandomVerticalFlip(p=0.5),
            _rotate90_choice(),
            T.RandomAffine(degrees=0, translate=(0.05, 0.05), scale=(0.95, 1.05)),
            T.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1, hue=0.02),
        ]
    ops.append(T.ToTensor())
    ops.append(_normalization_for(architecture, mean, std))
    return T.Compose(ops)

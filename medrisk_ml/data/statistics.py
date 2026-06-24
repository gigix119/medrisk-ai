"""Normalization statistics, computed from the TRAINING split only.

Computing these from validation or test data would leak distributional information into
the preprocessing pipeline used to evaluate them - a subtle form of train/test
contamination. `compute_normalization_stats` enforces this at the code level by checking
the dataset's own declared `.split` attribute.
"""

from __future__ import annotations

import torch
from torch.utils.data import Dataset


def compute_normalization_stats(
    dataset: Dataset[tuple[torch.Tensor, int, str]],
    max_samples: int = 256,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Per-channel mean/std over up to `max_samples` images from `dataset`.

    `dataset` must yield images already scaled to [0, 1] (i.e. ToTensor with no Normalize
    applied yet) and must declare `dataset.split == "train"`.
    """
    split = getattr(dataset, "split", None)
    if split != "train":
        raise ValueError(
            f"Normalization stats must be computed from the training split only (got split={split!r})"
        )

    n = min(max_samples, len(dataset))  # type: ignore[arg-type]
    if n <= 0:
        raise ValueError("dataset is empty")

    channel_sum = torch.zeros(3, dtype=torch.float64)
    channel_sq_sum = torch.zeros(3, dtype=torch.float64)
    pixel_count = 0
    for i in range(n):
        image, _label, _sample_id = dataset[i]
        image64 = image.to(torch.float64)
        channel_sum += image64.sum(dim=(1, 2))
        channel_sq_sum += (image64**2).sum(dim=(1, 2))
        pixel_count += image64.shape[1] * image64.shape[2]

    mean = channel_sum / pixel_count
    variance = channel_sq_sum / pixel_count - mean**2
    std = torch.sqrt(torch.clamp(variance, min=1e-12))

    mean_tuple = (float(mean[0]), float(mean[1]), float(mean[2]))
    std_tuple = (float(std[0]), float(std[1]), float(std[2]))
    return mean_tuple, std_tuple

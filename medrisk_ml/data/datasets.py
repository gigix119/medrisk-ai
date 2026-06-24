"""Real PatchCamelyon (PCam) dataset wrapper, plus deterministic subset selection.

Wraps `torchvision.datasets.PCAM` so it returns the same `(tensor, label, sample_id)`
contract as `SyntheticHistopathologyDataset` - everything downstream (loaders, training
engine, evaluator) works against that contract and never needs to know which dataset is
in use.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import Dataset, Subset
from torchvision.datasets import PCAM

from medrisk_ml.constants import CLASS_NAMES
from medrisk_ml.types import SplitName

_SPLIT_MAP: dict[SplitName, str] = {"train": "train", "val": "val", "test": "test"}


class PCamDataset(Dataset[tuple[torch.Tensor, int, str]]):
    """Adapter around `torchvision.datasets.PCAM` exposing the project's dataset contract."""

    classes: tuple[str, str] = CLASS_NAMES

    def __init__(
        self,
        root: Path | str,
        split: SplitName,
        transform: Callable[[Any], torch.Tensor] | None = None,
        download: bool = False,
    ) -> None:
        if split not in _SPLIT_MAP:
            raise ValueError(f"Unknown split: {split!r}")
        self.split = split
        self._dataset = PCAM(
            root=str(root), split=_SPLIT_MAP[split], transform=transform, download=download
        )

    def __len__(self) -> int:
        return len(self._dataset)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int, str]:
        image, label = self._dataset[index]
        sample_id = f"pcam_{self.split}_{index:06d}"
        return image, int(label), sample_id


def deterministic_subset(dataset: Dataset[Any], size: int, seed: int) -> Subset[Any]:
    """An unbiased, seed-reproducible subset (a seeded random permutation, not the first N
    items - PCam's on-disk ordering is not class-balanced, so naive slicing would skew it).
    """
    n = len(dataset)  # type: ignore[arg-type]
    if size > n:
        raise ValueError(f"Requested subset size {size} exceeds dataset size {n}")
    indices = np.random.default_rng(seed).permutation(n)[:size].tolist()
    return Subset(dataset, indices)

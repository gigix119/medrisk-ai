"""DataLoader construction: reproducible worker seeding, safe defaults, no test leakage.

Training loaders shuffle; validation and test loaders never do (shuffling them would make
nothing wrong numerically, but it makes runs harder to diff/debug and per-sample prediction
exports harder to align - so we just don't).
"""

from __future__ import annotations

from typing import Any

import torch
from torch.utils.data import DataLoader, Dataset

from medrisk_ml.utils.reproducibility import seed_worker


def build_loader(
    dataset: Dataset[Any],
    split: str,
    batch_size: int,
    num_workers: int = 0,
    pin_memory: bool = False,
    persistent_workers: bool = False,
    prefetch_factor: int | None = None,
    seed: int = 42,
) -> DataLoader[Any]:
    if num_workers == 0 and persistent_workers:
        raise ValueError("persistent_workers requires num_workers > 0")
    if num_workers == 0 and prefetch_factor is not None:
        raise ValueError("prefetch_factor requires num_workers > 0")

    shuffle = split == "train"
    kwargs: dict[str, Any] = {
        "batch_size": batch_size,
        "shuffle": shuffle,
        "num_workers": num_workers,
        "pin_memory": pin_memory,
        "drop_last": False,
    }
    if shuffle:
        generator = torch.Generator()
        generator.manual_seed(seed)
        kwargs["generator"] = generator
    if num_workers > 0:
        kwargs["worker_init_fn"] = seed_worker
        kwargs["persistent_workers"] = persistent_workers
        if prefetch_factor is not None:
            kwargs["prefetch_factor"] = prefetch_factor
    return DataLoader(dataset, **kwargs)

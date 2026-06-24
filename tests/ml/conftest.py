"""Shared fixtures for medrisk_ml tests: deterministic synthetic data, CPU device, tiny configs.

All ML tests run on CPU, with no network access and no real PCam data - see
docs/experiment-protocol.md and the module docstrings under medrisk_ml/data/synthetic.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import torch
import yaml

from medrisk_ml.data.synthetic import SyntheticHistopathologyDataset
from medrisk_ml.utils.device import ResolvedDevice

TEST_IMAGE_SIZE = 64


@pytest.fixture
def cpu_device() -> ResolvedDevice:
    return ResolvedDevice(
        device=torch.device("cpu"), requested="cpu", device_name="CPU", device_count=1
    )


@pytest.fixture
def synthetic_train_dataset() -> SyntheticHistopathologyDataset:
    return SyntheticHistopathologyDataset(
        "train", num_samples=16, seed=123, image_size=TEST_IMAGE_SIZE
    )


@pytest.fixture
def synthetic_val_dataset() -> SyntheticHistopathologyDataset:
    return SyntheticHistopathologyDataset(
        "val", num_samples=8, seed=123, image_size=TEST_IMAGE_SIZE
    )


@pytest.fixture
def minimal_config_dict() -> dict[str, Any]:
    return {
        "experiment": {"name": "unit-test", "seed": 7, "output_dir": "artifacts/experiments"},
        "data": {
            "dataset_name": "synthetic",
            "data_dir": "data/external/pcam",
            "synthetic": True,
            "smoke_mode": True,
            "train_subset_size": 16,
            "validation_subset_size": 8,
            "test_subset_size": 8,
            "image_size": TEST_IMAGE_SIZE,
        },
        "model": {"architecture": "baseline_cnn", "dropout": 0.1},
        "training": {"epochs": 1, "batch_size": 4, "learning_rate": 0.01},
    }


@pytest.fixture
def minimal_config_path(tmp_path: Path, minimal_config_dict: dict[str, Any]) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(minimal_config_dict), encoding="utf-8")
    return path

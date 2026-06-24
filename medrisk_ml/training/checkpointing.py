"""Checkpoint save/load with integrity hashing and defensive validation on load.

Checkpoints store `state_dict`s (never arbitrary pickled custom objects) plus the metadata
needed to reconstruct and audit the run: architecture, configs, class names, normalization,
threshold, calibration, git commit, timestamp. Loading is always `weights_only=True`
(PyTorch's restricted unpickler) - safe here because nothing in the payload is a custom
class, only tensors/str/int/float/bool/None/list/dict.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from medrisk_ml.utils.hashing import sha256_file

_REQUIRED_KEYS = (
    "model_state_dict",
    "epoch",
    "global_step",
    "best_metric",
    "architecture",
    "model_config",
    "training_config",
    "class_names",
    "normalization",
    "threshold",
    "calibration_metadata",
    "git_commit",
    "created_at",
)


class CheckpointError(ValueError):
    """Raised when a checkpoint file is missing required fields or doesn't match expectations."""


@dataclass
class CheckpointPayload:
    model_state_dict: dict[str, Any]
    optimizer_state_dict: dict[str, Any] | None
    scheduler_state_dict: dict[str, Any] | None
    epoch: int
    global_step: int
    best_metric: float | None
    architecture: str
    model_config: dict[str, Any]
    training_config: dict[str, Any]
    class_names: tuple[str, str]
    normalization: dict[str, Any]
    threshold: float
    calibration_metadata: dict[str, Any] | None
    git_commit: str | None
    created_at: str


def save_checkpoint(path: Path, payload: CheckpointPayload) -> str:
    """Save `payload` to `path` and return the sha256 of the written file (also written to
    a `<path>.sha256` sidecar for quick external verification by the model registry).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": payload.model_state_dict,
            "optimizer_state_dict": payload.optimizer_state_dict,
            "scheduler_state_dict": payload.scheduler_state_dict,
            "epoch": payload.epoch,
            "global_step": payload.global_step,
            "best_metric": payload.best_metric,
            "architecture": payload.architecture,
            "model_config": payload.model_config,
            "training_config": payload.training_config,
            "class_names": list(payload.class_names),
            "normalization": payload.normalization,
            "threshold": payload.threshold,
            "calibration_metadata": payload.calibration_metadata,
            "git_commit": payload.git_commit,
            "created_at": payload.created_at,
        },
        path,
    )
    digest = sha256_file(path)
    path.with_suffix(path.suffix + ".sha256").write_text(digest, encoding="utf-8")
    return digest


def load_checkpoint(
    path: Path,
    map_location: str | torch.device = "cpu",
    expected_architecture: str | None = None,
) -> CheckpointPayload:
    if not path.is_file():
        raise CheckpointError(f"Checkpoint not found: {path}")

    raw: dict[str, Any] = torch.load(path, map_location=map_location, weights_only=True)
    missing = [key for key in _REQUIRED_KEYS if key not in raw]
    if missing:
        raise CheckpointError(f"Checkpoint {path} is missing required field(s): {missing}")
    if expected_architecture is not None and raw["architecture"] != expected_architecture:
        raise CheckpointError(
            f"Checkpoint architecture mismatch: expected {expected_architecture!r}, found {raw['architecture']!r}"
        )

    class_names = tuple(raw["class_names"])
    if len(class_names) != 2:
        raise CheckpointError(f"Checkpoint {path} has invalid class_names: {raw['class_names']!r}")

    return CheckpointPayload(
        model_state_dict=raw["model_state_dict"],
        optimizer_state_dict=raw.get("optimizer_state_dict"),
        scheduler_state_dict=raw.get("scheduler_state_dict"),
        epoch=raw["epoch"],
        global_step=raw["global_step"],
        best_metric=raw["best_metric"],
        architecture=raw["architecture"],
        model_config=raw["model_config"],
        training_config=raw["training_config"],
        class_names=(class_names[0], class_names[1]),
        normalization=raw["normalization"],
        threshold=raw["threshold"],
        calibration_metadata=raw["calibration_metadata"],
        git_commit=raw["git_commit"],
        created_at=raw["created_at"],
    )

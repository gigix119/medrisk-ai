from __future__ import annotations

from pathlib import Path

import pytest
import torch

from medrisk_ml.models.baseline_cnn import BaselineCNN, BaselineCNNConfig
from medrisk_ml.training.checkpointing import (
    CheckpointError,
    CheckpointPayload,
    load_checkpoint,
    save_checkpoint,
)
from medrisk_ml.utils.hashing import sha256_file


def _make_payload(**overrides: object) -> CheckpointPayload:
    model = BaselineCNN(BaselineCNNConfig())
    defaults: dict[str, object] = {
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": None,
        "scheduler_state_dict": None,
        "epoch": 1,
        "global_step": 10,
        "best_metric": 0.9,
        "architecture": "baseline_cnn",
        "model_config": {"dropout": 0.3},
        "training_config": {"epochs": 1},
        "class_names": ("negative", "positive"),
        "normalization": {"scheme": "imagenet"},
        "threshold": 0.5,
        "calibration_metadata": {"temperature": 1.23},
        "git_commit": "abc123",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    defaults.update(overrides)
    return CheckpointPayload(**defaults)  # type: ignore[arg-type]


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    payload = _make_payload()
    checkpoint_path = tmp_path / "best.pt"
    save_checkpoint(checkpoint_path, payload)

    loaded = load_checkpoint(checkpoint_path)
    assert loaded.architecture == "baseline_cnn"
    assert loaded.epoch == 1
    assert loaded.threshold == 0.5
    assert loaded.class_names == ("negative", "positive")
    assert loaded.calibration_metadata == {"temperature": 1.23}
    assert set(loaded.model_state_dict.keys()) == set(payload.model_state_dict.keys())


def test_sha256_sidecar_matches_file(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "best.pt"
    digest = save_checkpoint(checkpoint_path, _make_payload())
    sidecar_path = checkpoint_path.with_suffix(checkpoint_path.suffix + ".sha256")
    assert sidecar_path.is_file()
    assert sidecar_path.read_text(encoding="utf-8").strip() == digest
    assert digest == sha256_file(checkpoint_path)


def test_load_missing_checkpoint_raises(tmp_path: Path) -> None:
    with pytest.raises(CheckpointError):
        load_checkpoint(tmp_path / "does_not_exist.pt")


def test_load_rejects_architecture_mismatch(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "best.pt"
    save_checkpoint(checkpoint_path, _make_payload(architecture="baseline_cnn"))
    with pytest.raises(CheckpointError):
        load_checkpoint(checkpoint_path, expected_architecture="resnet18")


def test_load_rejects_missing_required_fields(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "incomplete.pt"
    torch.save({"model_state_dict": {}, "architecture": "baseline_cnn"}, checkpoint_path)
    with pytest.raises(CheckpointError):
        load_checkpoint(checkpoint_path)

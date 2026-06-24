from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from medrisk_ml.models.baseline_cnn import BaselineCNN, BaselineCNNConfig
from medrisk_ml.registry.bundle import build_bundle, verify_bundle
from medrisk_ml.registry.manifest import ModelManifest
from medrisk_ml.registry.registry import ModelRegistrationError, ModelRegistry
from medrisk_ml.training.checkpointing import CheckpointPayload, save_checkpoint

IMAGE_SIZE = 32


def _make_checkpoint(path: Path) -> str:
    model = BaselineCNN(BaselineCNNConfig())
    payload = CheckpointPayload(
        model_state_dict=model.state_dict(),
        optimizer_state_dict=None,
        scheduler_state_dict=None,
        epoch=1,
        global_step=1,
        best_metric=0.9,
        architecture="baseline_cnn",
        model_config={"dropout": 0.3},
        training_config={"epochs": 1},
        class_names=("negative", "positive"),
        normalization={"mean": [0.5, 0.5, 0.5], "std": [0.25, 0.25, 0.25]},
        threshold=0.5,
        calibration_metadata=None,
        git_commit="abc123",
        created_at="2026-01-01T00:00:00+00:00",
    )
    return save_checkpoint(path, payload)


def _make_manifest(
    checkpoint_hash: str, version: str = "0.1.0", **overrides: object
) -> ModelManifest:
    defaults: dict[str, object] = {
        "model_id": f"unit-test-model:{version}",
        "model_name": "unit-test-model",
        "model_version": version,
        "architecture": "baseline_cnn",
        "checkpoint_sha256": checkpoint_hash,
        "dataset_name": "synthetic",
        "dataset_version": "synthetic-v1",
        "dataset_mode": "synthetic",
        "input_height": IMAGE_SIZE,
        "input_width": IMAGE_SIZE,
        "input_channels": 3,
        "class_names": ("negative", "positive"),
        "positive_class": "positive",
        "normalization": {"mean": [0.5, 0.5, 0.5], "std": [0.25, 0.25, 0.25]},
        "threshold": 0.5,
        "review_policy": None,
        "calibration": None,
        "validation_metrics": {"roc_auc": 0.95},
        "test_metrics": {"roc_auc": 0.93},
        "git_commit": "abc123",
        "created_at": "2026-01-01T00:00:00+00:00",
        "eligible_for_demo": False,
        "synthetic_only": True,
    }
    defaults.update(overrides)
    return ModelManifest(**defaults)  # type: ignore[arg-type]


def test_valid_model_registers(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "best.pt"
    checkpoint_hash = _make_checkpoint(checkpoint_path)
    registry = ModelRegistry(tmp_path / "model_registry")
    manifest = _make_manifest(checkpoint_hash)
    manifest_path = registry.register(checkpoint_path, manifest)
    assert manifest_path.is_file()
    loaded = registry.load_manifest("unit-test-model", "0.1.0")
    assert loaded.checkpoint_sha256 == checkpoint_hash


def test_missing_manifest_field_fails() -> None:
    with pytest.raises(ValidationError):
        ModelManifest(model_id="x")  # type: ignore[call-arg]


def test_corrupted_checkpoint_hash_fails(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "best.pt"
    real_hash = _make_checkpoint(checkpoint_path)
    registry = ModelRegistry(tmp_path / "model_registry")
    manifest = _make_manifest(checkpoint_hash="0" * 64)
    assert real_hash != manifest.checkpoint_sha256
    with pytest.raises(ModelRegistrationError):
        registry.register(checkpoint_path, manifest)


def test_synthetic_model_cannot_be_eligible_for_demo(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "best.pt"
    checkpoint_hash = _make_checkpoint(checkpoint_path)
    registry = ModelRegistry(tmp_path / "model_registry")
    manifest = _make_manifest(checkpoint_hash, synthetic_only=True, eligible_for_demo=True)
    with pytest.raises(ModelRegistrationError):
        registry.register(checkpoint_path, manifest)


def test_duplicate_version_fails_safely(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "best.pt"
    checkpoint_hash = _make_checkpoint(checkpoint_path)
    registry = ModelRegistry(tmp_path / "model_registry")
    manifest = _make_manifest(checkpoint_hash)
    registry.register(checkpoint_path, manifest)
    with pytest.raises(ModelRegistrationError):
        registry.register(checkpoint_path, manifest)


# --- bundle ---------------------------------------------------------------------------


def test_valid_bundle_verifies(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "best.pt"
    checkpoint_hash = _make_checkpoint(checkpoint_path)
    manifest = _make_manifest(checkpoint_hash)
    bundle_dir = tmp_path / "bundle"
    build_bundle(checkpoint_path, manifest, bundle_dir, model_card_markdown="# Card")
    result = verify_bundle(bundle_dir)
    assert result.valid
    assert result.smoke_inference_ok
    assert result.errors == []


def test_bundle_missing_file_fails(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "best.pt"
    checkpoint_hash = _make_checkpoint(checkpoint_path)
    manifest = _make_manifest(checkpoint_hash)
    bundle_dir = tmp_path / "bundle"
    build_bundle(checkpoint_path, manifest, bundle_dir, model_card_markdown="# Card")

    (bundle_dir / "calibration.json").unlink()
    result = verify_bundle(bundle_dir)
    assert not result.valid
    assert any("calibration.json" in error for error in result.errors)


def test_bundle_checksum_mismatch_fails(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "best.pt"
    checkpoint_hash = _make_checkpoint(checkpoint_path)
    manifest = _make_manifest(checkpoint_hash)
    bundle_dir = tmp_path / "bundle"
    build_bundle(checkpoint_path, manifest, bundle_dir, model_card_markdown="# Card")

    (bundle_dir / "model_card.md").write_text("# Tampered", encoding="utf-8")
    result = verify_bundle(bundle_dir)
    assert not result.valid
    assert any("Checksum mismatch" in error for error in result.errors)


def test_bundle_smoke_inference_succeeds(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "best.pt"
    checkpoint_hash = _make_checkpoint(checkpoint_path)
    manifest = _make_manifest(checkpoint_hash)
    bundle_dir = tmp_path / "bundle"
    build_bundle(checkpoint_path, manifest, bundle_dir, model_card_markdown="# Card")
    result = verify_bundle(bundle_dir)
    assert result.smoke_inference_ok is True


def test_verify_bundle_on_nonexistent_directory_fails_cleanly(tmp_path: Path) -> None:
    result = verify_bundle(tmp_path / "does_not_exist")
    assert not result.valid
    assert result.errors

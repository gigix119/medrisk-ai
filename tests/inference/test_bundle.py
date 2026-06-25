"""Unit tests for medrisk_inference.bundle (Phase 3 bundle validation)."""

from __future__ import annotations

from pathlib import Path

import pytest

from medrisk_inference.bundle import load_bundle
from medrisk_inference.config import InferenceConfig
from medrisk_inference.exceptions import BundleInvalidError
from medrisk_ml.utils.hashing import sha256_file
from tests.inference.fixtures.builder import build_constant_output_bundle


def _retamper_checksum(bundle_dir: Path, filename: str) -> None:
    """Rewrite SHA256SUMS' entry for `filename` to match its current (tampered) content,
    isolating a manifest-content failure from a checksum-mismatch failure."""
    checksums_path = bundle_dir / "SHA256SUMS"
    new_hash = sha256_file(bundle_dir / filename)
    lines = checksums_path.read_text(encoding="utf-8").splitlines()
    updated = [f"{new_hash}  {filename}" if line.endswith(filename) else line for line in lines]
    checksums_path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def _config(bundle_path: Path, **overrides: object) -> InferenceConfig:
    base = {"environment": "test", "model_bundle_path": str(bundle_path)}
    base.update(overrides)
    return InferenceConfig(**base)  # type: ignore[arg-type]


def test_valid_bundle_loads(bundle_dir: Path) -> None:
    loaded = load_bundle(bundle_dir, _config(bundle_dir))
    assert loaded.manifest.architecture == "baseline_cnn"
    assert loaded.manifest.synthetic_only is True
    assert len(loaded.bundle_sha256) == 64


def test_missing_directory_fails(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises(BundleInvalidError):
        load_bundle(missing, _config(missing))


def test_missing_required_file_fails(bundle_dir: Path) -> None:
    (bundle_dir / "calibration.json").unlink()
    with pytest.raises(BundleInvalidError, match="Missing required file"):
        load_bundle(bundle_dir, _config(bundle_dir))


def test_checksum_mismatch_fails(bundle_dir: Path) -> None:
    (bundle_dir / "model_card.md").write_text("tampered", encoding="utf-8")
    with pytest.raises(BundleInvalidError, match="Checksum mismatch"):
        load_bundle(bundle_dir, _config(bundle_dir))


def test_synthetic_bundle_rejected_in_production(bundle_dir: Path) -> None:
    config = _config(bundle_dir, environment="production", allow_synthetic_model=False)
    with pytest.raises(BundleInvalidError, match="synthetic_only"):
        load_bundle(bundle_dir, config)


def test_synthetic_bundle_rejected_in_development_without_opt_in(bundle_dir: Path) -> None:
    config = _config(bundle_dir, environment="development", allow_synthetic_model=False)
    with pytest.raises(BundleInvalidError, match="synthetic_only"):
        load_bundle(bundle_dir, config)


def test_synthetic_bundle_allowed_in_development_with_opt_in(bundle_dir: Path) -> None:
    config = _config(bundle_dir, environment="development", allow_synthetic_model=True)
    loaded = load_bundle(bundle_dir, config)
    assert loaded.manifest.synthetic_only is True


def test_non_eligible_demo_bundle_with_synthetic_true_is_consistent(bundle_dir: Path) -> None:
    # Built fixture is synthetic_only=True, eligible_for_demo=False - the only valid combo
    # for a synthetic bundle. Sanity-check the invariant the fixture itself relies on.
    loaded = load_bundle(bundle_dir, _config(bundle_dir))
    assert not (loaded.manifest.synthetic_only and loaded.manifest.eligible_for_demo)


def test_unknown_architecture_in_manifest_fails(bundle_dir: Path) -> None:
    manifest_path = bundle_dir / "manifest.json"
    tampered = manifest_path.read_text(encoding="utf-8").replace(
        '"architecture": "baseline_cnn"', '"architecture": "made_up_architecture"'
    )
    manifest_path.write_text(tampered, encoding="utf-8")
    _retamper_checksum(bundle_dir, "manifest.json")

    with pytest.raises(BundleInvalidError, match="Unsupported architecture"):
        load_bundle(bundle_dir, _config(bundle_dir))


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    bundle_dir = build_constant_output_bundle(tmp_path, model_name="symlink-test")
    outside_target = tmp_path / "outside_secret.txt"
    outside_target.write_text("not part of the bundle", encoding="utf-8")

    victim = bundle_dir / "model_card.md"
    victim.unlink()
    try:
        victim.symlink_to(outside_target)
    except OSError:
        pytest.skip("Symlink creation is not permitted in this environment.")

    with pytest.raises(BundleInvalidError, match="symlink escape"):
        load_bundle(bundle_dir, _config(bundle_dir))

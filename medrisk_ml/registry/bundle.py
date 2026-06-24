"""Portable model bundle for future API integration: state_dict + metadata, no training code.

Building a bundle always ends with a self-verification pass that includes one smoke
inference (a random tensor of the declared input shape) - registering a model that can't
actually produce output is a bug we want to catch immediately, not discover in Phase 3.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import torch

from medrisk_ml.models.factory import build_model
from medrisk_ml.registry.manifest import ModelManifest
from medrisk_ml.training.checkpointing import load_checkpoint
from medrisk_ml.utils.hashing import sha256_file
from medrisk_ml.utils.logging import get_logger

logger = get_logger(__name__)

BUNDLE_FILES = (
    "model_state.pt",
    "manifest.json",
    "preprocessing.json",
    "threshold.json",
    "calibration.json",
    "model_card.md",
)
_KNOWN_ARCHITECTURES = ("baseline_cnn", "resnet18")


class BundleError(ValueError):
    """Raised when bundle creation or self-verification fails."""


@dataclass(frozen=True)
class BundleVerificationResult:
    valid: bool
    errors: list[str]
    smoke_inference_ok: bool


def build_bundle(
    checkpoint_path: Path, manifest: ModelManifest, output_dir: Path, model_card_markdown: str
) -> Path:
    payload = load_checkpoint(checkpoint_path, expected_architecture=manifest.architecture)
    output_dir.mkdir(parents=True, exist_ok=True)

    torch.save(payload.model_state_dict, output_dir / "model_state.pt")
    (output_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    (output_dir / "preprocessing.json").write_text(
        json.dumps(
            {
                "normalization": payload.normalization,
                "input_height": manifest.input_height,
                "input_width": manifest.input_width,
                "input_channels": manifest.input_channels,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "threshold.json").write_text(
        json.dumps(
            {"threshold": payload.threshold, "review_policy": manifest.review_policy}, indent=2
        ),
        encoding="utf-8",
    )
    (output_dir / "calibration.json").write_text(
        json.dumps(payload.calibration_metadata or {}, indent=2), encoding="utf-8"
    )
    (output_dir / "model_card.md").write_text(model_card_markdown, encoding="utf-8")

    _write_checksums(output_dir)

    result = verify_bundle(output_dir)
    if not result.valid:
        raise BundleError(
            f"Bundle failed self-verification immediately after creation: {result.errors}"
        )
    return output_dir


def _write_checksums(output_dir: Path) -> Path:
    checksums_path = output_dir / "SHA256SUMS"
    lines = [
        f"{sha256_file(output_dir / filename)}  {filename}"
        for filename in BUNDLE_FILES
        if (output_dir / filename).is_file()
    ]
    checksums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksums_path


def verify_bundle(bundle_dir: Path) -> BundleVerificationResult:
    """Fails clearly (non-raising; returns `valid=False` with `errors`) when a required
    file is missing, a checksum doesn't match, the architecture is unsupported, the
    preprocessing metadata is invalid, or the model can't produce output.
    """
    errors: list[str] = []

    for filename in (*BUNDLE_FILES, "SHA256SUMS"):
        if not (bundle_dir / filename).is_file():
            errors.append(f"Missing required file: {filename}")
    if errors:
        return BundleVerificationResult(valid=False, errors=errors, smoke_inference_ok=False)

    for line in (bundle_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected_hash, filename = line.split("  ", 1)
        actual_hash = sha256_file(bundle_dir / filename)
        if actual_hash != expected_hash:
            errors.append(
                f"Checksum mismatch for {filename}: expected {expected_hash}, got {actual_hash}"
            )
    if errors:
        return BundleVerificationResult(valid=False, errors=errors, smoke_inference_ok=False)

    try:
        manifest = ModelManifest.model_validate_json(
            (bundle_dir / "manifest.json").read_text(encoding="utf-8")
        )
    except Exception as exc:
        return BundleVerificationResult(
            valid=False, errors=[f"Invalid manifest.json: {exc}"], smoke_inference_ok=False
        )

    if manifest.architecture not in _KNOWN_ARCHITECTURES:
        return BundleVerificationResult(
            valid=False,
            errors=[f"Unsupported architecture in manifest: {manifest.architecture}"],
            smoke_inference_ok=False,
        )

    try:
        preprocessing = json.loads((bundle_dir / "preprocessing.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return BundleVerificationResult(
            valid=False, errors=[f"Invalid preprocessing.json: {exc}"], smoke_inference_ok=False
        )

    missing_keys = [
        k for k in ("input_height", "input_width", "input_channels") if k not in preprocessing
    ]
    if missing_keys:
        errors.append(f"preprocessing.json missing required key(s): {missing_keys}")
        return BundleVerificationResult(valid=False, errors=errors, smoke_inference_ok=False)

    smoke_ok = False
    try:
        model, _metadata = build_model(
            manifest.architecture,  # type: ignore[arg-type]
            pretrained=False,
            input_channels=preprocessing["input_channels"],
            image_size=preprocessing["input_height"],
        )
        state_dict = torch.load(
            bundle_dir / "model_state.pt", map_location="cpu", weights_only=True
        )
        model.load_state_dict(state_dict)
        model.eval()
        dummy = torch.randn(
            1,
            preprocessing["input_channels"],
            preprocessing["input_height"],
            preprocessing["input_width"],
        )
        with torch.no_grad():
            output = model(dummy)
        if not torch.isfinite(output).all():
            errors.append("Smoke inference produced non-finite output")
        else:
            smoke_ok = True
    except Exception as exc:  # reported in the result, not raised
        errors.append(f"Smoke inference failed: {exc}")

    return BundleVerificationResult(valid=not errors, errors=errors, smoke_inference_ok=smoke_ok)

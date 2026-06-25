"""Phase 3 bundle loading: re-validates a Phase 2 model bundle and applies the additional
checks Phase 3 cares about (synthetic-in-production rejection, symlink-escape rejection,
class/positive-class consistency) on top of medrisk_ml's own checksum + smoke-inference
verification.

The model bundle path is never accepted from API users - only from application
configuration (`InferenceConfig.model_bundle_path`, itself sourced from `Settings`/the CLI).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from medrisk_inference.config import InferenceConfig
from medrisk_inference.constants import BUNDLE_FILES
from medrisk_inference.exceptions import BundleInvalidError
from medrisk_ml.registry.bundle import verify_bundle
from medrisk_ml.registry.manifest import ModelManifest
from medrisk_ml.utils.hashing import sha256_file


@dataclass(frozen=True)
class LoadedBundle:
    bundle_dir: Path
    manifest: ModelManifest
    preprocessing: dict[str, Any]
    threshold_data: dict[str, Any]
    calibration: dict[str, Any]
    model_card: str
    bundle_sha256: str


def load_bundle(bundle_path: str | Path, config: InferenceConfig) -> LoadedBundle:
    """Validate and load a model bundle directory. Raises `BundleInvalidError` on any
    failure - callers (the runtime / deployment service) decide how to react.
    """
    bundle_dir = Path(bundle_path)
    if not bundle_dir.is_dir():
        raise BundleInvalidError(f"Model bundle directory does not exist: {bundle_dir}")

    _ensure_no_symlink_escape(bundle_dir)

    result = verify_bundle(bundle_dir)
    if not result.valid:
        raise BundleInvalidError(
            f"Model bundle failed verification: {'; '.join(result.errors)}",
            details={"errors": result.errors},
        )

    manifest = ModelManifest.model_validate_json(
        (bundle_dir / "manifest.json").read_text(encoding="utf-8")
    )

    if manifest.input_height != manifest.input_width:
        # medrisk_ml.data.transforms.build_transform only supports a single square
        # `image_size`, matching every architecture/preprocessing pipeline Phase 2 produces.
        raise BundleInvalidError(
            "Non-square model input is not supported by the inference preprocessing "
            f"pipeline: {manifest.input_height}x{manifest.input_width}"
        )

    if manifest.positive_class not in manifest.class_names:
        raise BundleInvalidError(
            f"positive_class {manifest.positive_class!r} is not in class_names "
            f"{manifest.class_names!r}"
        )

    if manifest.synthetic_only and manifest.eligible_for_demo:
        # Already prevented at registration time (ModelRegistry.register), but a bundle
        # could in principle be hand-edited on disk - re-check defensively at load time.
        raise BundleInvalidError(
            "Bundle is invalid: synthetic_only and eligible_for_demo cannot both be true."
        )

    if manifest.synthetic_only and not config.synthetic_model_allowed:
        raise BundleInvalidError(
            "Bundle is synthetic_only=true, which is not permitted under the current "
            f"environment ({config.environment!r}) / ALLOW_SYNTHETIC_MODEL configuration."
        )

    _validate_normalization(manifest.normalization)

    preprocessing = json.loads((bundle_dir / "preprocessing.json").read_text(encoding="utf-8"))
    threshold_data = json.loads((bundle_dir / "threshold.json").read_text(encoding="utf-8"))
    calibration = json.loads((bundle_dir / "calibration.json").read_text(encoding="utf-8"))
    model_card = (bundle_dir / "model_card.md").read_text(encoding="utf-8")

    return LoadedBundle(
        bundle_dir=bundle_dir,
        manifest=manifest,
        preprocessing=preprocessing,
        threshold_data=threshold_data,
        calibration=calibration,
        model_card=model_card,
        bundle_sha256=sha256_file(bundle_dir / "SHA256SUMS"),
    )


def _ensure_no_symlink_escape(bundle_dir: Path) -> None:
    resolved_root = bundle_dir.resolve()
    for filename in BUNDLE_FILES:
        candidate = bundle_dir / filename
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if resolved_root not in (resolved, *resolved.parents):
            raise BundleInvalidError(
                f"Bundle file {filename!r} resolves outside the bundle directory "
                "(symlink escape)."
            )


def _validate_normalization(normalization: dict[str, Any]) -> None:
    if normalization.get("scheme") == "imagenet":
        return
    mean = normalization.get("mean")
    std = normalization.get("std")
    if (
        not isinstance(mean, list)
        or not isinstance(std, list)
        or len(mean) != 3
        or len(std) != 3
        or not all(isinstance(v, int | float) for v in (*mean, *std))
    ):
        raise BundleInvalidError(
            "manifest normalization must be either {'scheme': 'imagenet'} or "
            "{'mean': [3 floats], 'std': [3 floats]}, "
            f"got: {normalization!r}"
        )

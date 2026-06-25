"""Builds a tiny, deterministic, synthetic model bundle for tests.

Reuses the exact Phase 2 checkpoint/bundle machinery (medrisk_ml.training.checkpointing,
medrisk_ml.registry.bundle) rather than hand-rolling bundle files, so the fixture stays
honest about what a real bundle looks like - and gets the same self-verification pass a
real registered model goes through.

The classifier's final Linear layer is zeroed (weight=0, bias=0), so the model's output
logit is exactly 0.0 for *any* input, at *any* temperature. That makes calibration/
threshold/review-policy behavior fully deterministic in tests without needing a trained
model: the calibrated probability is always exactly 0.5, and callers choose `threshold`/
`review_policy` per test to land that fixed 0.5 in whichever decision band they want to
exercise.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import torch

from medrisk_ml.constants import MEDICAL_DISCLAIMER
from medrisk_ml.models.factory import build_model
from medrisk_ml.registry.bundle import build_bundle
from medrisk_ml.registry.manifest import ModelManifest
from medrisk_ml.training.checkpointing import CheckpointPayload, save_checkpoint
from medrisk_ml.types import DatasetName
from medrisk_ml.utils.hashing import sha256_file

DEFAULT_IMAGE_SIZE = 32
DEFAULT_NORMALIZATION: dict[str, Any] = {"mean": [0.5, 0.5, 0.5], "std": [0.25, 0.25, 0.25]}
CLASS_NAMES = ("negative", "positive")


def build_constant_output_bundle(
    parent_dir: Path,
    *,
    model_name: str = "test-constant-cnn",
    model_version: str = "0.0.1-test",
    image_size: int = DEFAULT_IMAGE_SIZE,
    threshold: float = 0.5,
    review_policy: dict[str, Any] | None = None,
    calibration: dict[str, Any] | None = None,
    synthetic_only: bool = True,
    eligible_for_demo: bool = False,
    dataset_mode: DatasetName = "synthetic",
) -> Path:
    """Build, self-verify, and return the path to a constant-output bundle.

    `parent_dir` is a scratch directory (typically `tmp_path`); the bundle itself is written
    to `parent_dir/model_name/model_version`, matching the real ModelRegistry's layout.
    """
    model, _metadata = build_model("baseline_cnn", input_channels=3, image_size=image_size)
    classifier_linear = model.classifier[-1]
    with torch.no_grad():
        classifier_linear.weight.zero_()
        classifier_linear.bias.zero_()

    created_at = datetime.now(UTC).isoformat()
    checkpoint_path = parent_dir / f"_{model_name}_{model_version}_checkpoint.pt"
    save_checkpoint(
        checkpoint_path,
        CheckpointPayload(
            model_state_dict=model.state_dict(),
            optimizer_state_dict=None,
            scheduler_state_dict=None,
            epoch=0,
            global_step=0,
            best_metric=None,
            architecture="baseline_cnn",
            model_config={"input_channels": 3, "dropout": 0.0},
            training_config={},
            class_names=CLASS_NAMES,
            normalization=DEFAULT_NORMALIZATION,
            threshold=threshold,
            calibration_metadata=calibration,
            git_commit=None,
            created_at=created_at,
        ),
    )

    manifest = ModelManifest(
        model_id=f"{model_name}:{model_version}",
        model_name=model_name,
        model_version=model_version,
        architecture="baseline_cnn",
        checkpoint_sha256=sha256_file(checkpoint_path),
        dataset_name="synthetic",
        dataset_version="synthetic-v1",
        dataset_mode=dataset_mode,
        input_height=image_size,
        input_width=image_size,
        input_channels=3,
        class_names=CLASS_NAMES,
        positive_class="positive",
        normalization=DEFAULT_NORMALIZATION,
        threshold=threshold,
        review_policy=review_policy,
        calibration=calibration,
        validation_metrics={},
        test_metrics=None,
        git_commit=None,
        created_at=created_at,
        medical_disclaimer=MEDICAL_DISCLAIMER,
        eligible_for_demo=eligible_for_demo,
        synthetic_only=synthetic_only,
    )

    bundle_dir = parent_dir / model_name / model_version
    build_bundle(
        checkpoint_path,
        manifest,
        bundle_dir,
        model_card_markdown=f"# {model_name}\n\nDeterministic test fixture bundle - "
        f"not a trained model. {MEDICAL_DISCLAIMER}\n",
    )
    return bundle_dir

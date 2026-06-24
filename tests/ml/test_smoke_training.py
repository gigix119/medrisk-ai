"""End-to-end smoke pipeline test: synthetic data through training, evaluation,
calibration, Grad-CAM, and a verified model bundle - small enough for CI.

SYNTHETIC DATA - the roc_auc sanity check below confirms the pipeline learns *something*
non-random; it is not, and must never be cited as, a medical performance result.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import torch

from medrisk_ml.data.loaders import build_loader
from medrisk_ml.data.synthetic import SyntheticHistopathologyDataset
from medrisk_ml.data.transforms import build_transform
from medrisk_ml.evaluation.evaluator import run_full_evaluation
from medrisk_ml.explainability.gradcam import GradCAM
from medrisk_ml.explainability.visualization import save_overlay
from medrisk_ml.models.factory import build_model, get_target_layer
from medrisk_ml.registry.bundle import build_bundle, verify_bundle
from medrisk_ml.registry.manifest import ModelManifest
from medrisk_ml.training.checkpointing import load_checkpoint
from medrisk_ml.training.engine import evaluate, train_one_epoch
from medrisk_ml.training.losses import build_loss
from medrisk_ml.training.optimizer import build_optimizer
from medrisk_ml.training.scheduler import build_scheduler
from medrisk_ml.training.trainer import fit
from medrisk_ml.utils.device import ResolvedDevice
from medrisk_ml.utils.hashing import sha256_file
from medrisk_ml.utils.reproducibility import set_seed

IMAGE_SIZE = 32
_CPU = ResolvedDevice(
    device=torch.device("cpu"), requested="cpu", device_name="CPU", device_count=1
)


def test_one_tiny_training_epoch_executes() -> None:
    dataset = SyntheticHistopathologyDataset("train", 8, seed=3, image_size=IMAGE_SIZE)
    loader = build_loader(dataset, "train", batch_size=4, seed=3)
    model, _metadata = build_model("baseline_cnn", image_size=IMAGE_SIZE)
    optimizer = build_optimizer(model, "adamw", learning_rate=0.01)
    result = train_one_epoch(model, loader, optimizer, build_loss(), _CPU)
    assert result.skipped_batches == 0
    assert len(result.sample_ids) == 8
    assert result.logits.shape == (8,)


def test_validation_epoch_executes() -> None:
    dataset = SyntheticHistopathologyDataset("val", 8, seed=3, image_size=IMAGE_SIZE)
    loader = build_loader(dataset, "val", batch_size=4, seed=3)
    model, _metadata = build_model("baseline_cnn", image_size=IMAGE_SIZE)
    result = evaluate(model, loader, build_loss(), _CPU)
    assert len(result.sample_ids) == 8


def test_non_finite_loss_is_detected_and_aborts() -> None:
    class _AlwaysNaNModel(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.linear = torch.nn.Linear(3 * IMAGE_SIZE * IMAGE_SIZE, 1)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.linear(x.flatten(1)) * float("nan")

    dataset = SyntheticHistopathologyDataset("train", 8, seed=2, image_size=IMAGE_SIZE)
    loader = build_loader(dataset, "train", batch_size=4, seed=2)
    model = _AlwaysNaNModel()
    optimizer = build_optimizer(model, "adamw", learning_rate=0.001)

    with pytest.raises(RuntimeError, match="non-finite"):
        train_one_epoch(model, loader, optimizer, build_loss(), _CPU, max_consecutive_non_finite=1)


def test_full_synthetic_smoke_pipeline(tmp_path: Path) -> None:
    set_seed(42, deterministic=False)
    mean, std = (0.5, 0.5, 0.5), (0.25, 0.25, 0.25)
    train_transform = build_transform("train", "baseline_cnn", IMAGE_SIZE, mean, std)
    eval_transform = build_transform("test", "baseline_cnn", IMAGE_SIZE, mean, std)

    train_ds = SyntheticHistopathologyDataset(
        "train", 24, seed=1, image_size=IMAGE_SIZE, transform=train_transform
    )
    val_ds = SyntheticHistopathologyDataset(
        "val", 12, seed=1, image_size=IMAGE_SIZE, transform=eval_transform
    )
    test_ds = SyntheticHistopathologyDataset(
        "test", 12, seed=1, image_size=IMAGE_SIZE, transform=eval_transform
    )
    display_ds = SyntheticHistopathologyDataset("test", 12, seed=1, image_size=IMAGE_SIZE)

    train_loader = build_loader(train_ds, "train", batch_size=4, seed=1)
    val_loader = build_loader(val_ds, "val", batch_size=4, seed=1)
    test_loader = build_loader(test_ds, "test", batch_size=4, seed=1)

    model, _metadata = build_model("baseline_cnn", dropout=0.1, image_size=IMAGE_SIZE)
    loss_fn = build_loss()
    optimizer = build_optimizer(model, "adamw", learning_rate=0.01)
    scheduler = build_scheduler(optimizer, "none")

    experiment_dir = tmp_path / "experiment"
    training_result = fit(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        optimizer=optimizer,
        scheduler=scheduler,
        loss_fn=loss_fn,
        device=_CPU,
        epochs=3,
        experiment_dir=experiment_dir,
        architecture="baseline_cnn",
        model_config={"dropout": 0.1},
        training_config={"epochs": 3},
        class_names=("negative", "positive"),
        tensorboard=False,
    )

    assert training_result.best_checkpoint_path.is_file()
    assert training_result.last_checkpoint_path.is_file()
    assert (experiment_dir / "training_history.json").is_file()
    assert (experiment_dir / "training_history.csv").is_file()
    assert len(training_result.history) == 3

    checkpoint_payload = load_checkpoint(
        training_result.best_checkpoint_path, expected_architecture="baseline_cnn"
    )
    model.load_state_dict(checkpoint_payload.model_state_dict)

    evaluation_result = run_full_evaluation(
        model=model,
        val_loader=val_loader,
        test_loader=test_loader,
        loss_fn=loss_fn,
        device=_CPU,
        output_dir=experiment_dir,
        class_names=("negative", "positive"),
        threshold_strategy="max_f1",
        calibrate=True,
        bootstrap_samples=5,
        seed=1,
    )
    assert evaluation_result.predictions_path.is_file()
    assert evaluation_result.report_path.is_file()
    assert evaluation_result.metrics_path.is_file()
    assert evaluation_result.temperature is not None
    assert evaluation_result.bootstrap is not None

    # The synthetic task (diffuse noise vs. a centered bright blob) is trivially learnable -
    # this is a sanity check that *something* was learned, not a medical-performance claim.
    roc_auc = evaluation_result.test_metrics["roc_auc"]
    assert roc_auc is not None and roc_auc >= 0.6  # type: ignore[operator]

    target_layer = get_target_layer(model, "baseline_cnn")
    model_input_image, _label, _sample_id = test_ds[0]
    display_image_tensor, _label2, _sample_id2 = display_ds[0]
    with GradCAM(model, target_layer) as cam:
        heatmap = cam.generate(model_input_image.unsqueeze(0))
    display_image = (
        (display_image_tensor.permute(1, 2, 0).numpy() * 255).clip(0, 255).astype("uint8")
    )
    gradcam_path = experiment_dir / "gradcam" / "sample.png"
    save_overlay(display_image, heatmap, gradcam_path)
    assert gradcam_path.is_file()

    manifest = ModelManifest(
        model_id="smoke-test-model:0.0.1",
        model_name="smoke-test-model",
        model_version="0.0.1",
        architecture="baseline_cnn",
        checkpoint_sha256=sha256_file(training_result.best_checkpoint_path),
        dataset_name="synthetic",
        dataset_version="synthetic-v1",
        dataset_mode="synthetic",
        input_height=IMAGE_SIZE,
        input_width=IMAGE_SIZE,
        input_channels=3,
        class_names=("negative", "positive"),
        positive_class="positive",
        normalization={"mean": list(mean), "std": list(std)},
        threshold=evaluation_result.threshold_result.threshold,
        review_policy=None,
        calibration={"temperature": evaluation_result.temperature},
        validation_metrics=evaluation_result.threshold_result.validation_metrics,
        test_metrics=evaluation_result.test_metrics,
        git_commit=None,
        created_at="2026-01-01T00:00:00+00:00",
        eligible_for_demo=False,
        synthetic_only=True,
    )
    bundle_dir = experiment_dir / "bundle"
    build_bundle(
        training_result.best_checkpoint_path,
        manifest,
        bundle_dir,
        model_card_markdown="# Smoke test model",
    )
    verification = verify_bundle(bundle_dir)
    assert verification.valid
    assert verification.smoke_inference_ok

"""Command-line entrypoint: `python -m medrisk_ml.cli <command> ...`.

Each subcommand is a thin wrapper around the rest of the package - this module owns
argument parsing, experiment/dataset wiring, and exit codes, not the underlying algorithms.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms as T

from medrisk_ml.config import ExperimentConfig, LoadedConfig, load_config
from medrisk_ml.constants import (
    ALLOW_DATA_DOWNLOAD_ENV_VAR,
    CLASS_NAMES,
    EXPERIMENT_REGISTRY_RELATIVE_PATH,
    GRADCAM_DISCLAIMER,
    REPO_ROOT,
    SYNTHETIC_DATA_WARNING,
)
from medrisk_ml.data.datasets import PCamDataset, deterministic_subset
from medrisk_ml.data.download import ensure_pcam
from medrisk_ml.data.loaders import build_loader
from medrisk_ml.data.metadata import (
    SplitReport,
    build_dataset_report,
    inspect_split,
    write_dataset_report,
)
from medrisk_ml.data.statistics import compute_normalization_stats
from medrisk_ml.data.synthetic import SyntheticHistopathologyDataset
from medrisk_ml.data.transforms import build_transform
from medrisk_ml.evaluation.evaluator import run_full_evaluation
from medrisk_ml.explainability.gradcam import GradCAM
from medrisk_ml.explainability.visualization import save_overlay
from medrisk_ml.models.factory import build_model, get_target_layer
from medrisk_ml.registry.bundle import build_bundle, verify_bundle
from medrisk_ml.registry.manifest import ExperimentRecord, ModelManifest
from medrisk_ml.registry.registry import ExperimentRegistry, ModelRegistry
from medrisk_ml.training.checkpointing import load_checkpoint, save_checkpoint
from medrisk_ml.training.losses import build_loss
from medrisk_ml.training.optimizer import build_optimizer
from medrisk_ml.training.scheduler import build_scheduler
from medrisk_ml.training.trainer import fit
from medrisk_ml.types import SplitName
from medrisk_ml.utils.device import resolve_device
from medrisk_ml.utils.hashing import sha256_file
from medrisk_ml.utils.logging import get_logger
from medrisk_ml.utils.reproducibility import collect_environment_metadata, set_seed

logger = get_logger("medrisk_ml.cli")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_experiment_id(name: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{name}-{timestamp}-{uuid.uuid4().hex[:6]}"


def _experiment_dir_for_id(experiment_id: str) -> Path:
    return REPO_ROOT / "artifacts" / "experiments" / experiment_id


def _load_experiment_config(experiment_dir: Path) -> LoadedConfig:
    config_path = experiment_dir / "resolved_config.yaml"
    if not config_path.is_file():
        raise FileNotFoundError(f"No resolved_config.yaml found for this experiment: {config_path}")
    return load_config(config_path)


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


# --- dataset/transform wiring -------------------------------------------------------


def _synthetic_split_size(cfg: ExperimentConfig, split: str) -> int:
    defaults = {"train": 256, "val": 64, "test": 64}
    configured = {
        "train": cfg.data.train_subset_size,
        "val": cfg.data.validation_subset_size,
        "test": cfg.data.test_subset_size,
    }
    return configured[split] or defaults[split]


def _pcam_subset_size(cfg: ExperimentConfig, split: str) -> int | None:
    configured = {
        "train": cfg.data.train_subset_size,
        "val": cfg.data.validation_subset_size,
        "test": cfg.data.test_subset_size,
    }
    return configured[split]


def _build_split_dataset(
    cfg: ExperimentConfig,
    loaded: LoadedConfig,
    split: SplitName,
    transform: Any,
    apply_subset: bool = True,
) -> Dataset[Any]:
    if cfg.data.dataset_name == "synthetic":
        n = _synthetic_split_size(cfg, split)
        return SyntheticHistopathologyDataset(
            split, n, cfg.experiment.seed, cfg.data.image_size, transform=transform
        )

    dataset: Dataset[Any] = PCamDataset(
        loaded.resolved_data_dir, split, transform=transform, download=False
    )
    if apply_subset:
        size = _pcam_subset_size(cfg, split)
        if size is not None:
            dataset = deterministic_subset(dataset, size, cfg.experiment.seed)
    return dataset


def _stats_for_architecture(
    cfg: ExperimentConfig, loaded: LoadedConfig
) -> tuple[tuple[float, float, float] | None, tuple[float, float, float] | None]:
    if cfg.model.architecture == "resnet18":
        return None, None
    stats_transform = T.Compose(
        [T.Resize((cfg.data.image_size, cfg.data.image_size)), T.ToTensor()]
    )
    raw_train_ds = _build_split_dataset(cfg, loaded, "train", stats_transform, apply_subset=False)
    return compute_normalization_stats(raw_train_ds)


def _build_datasets(
    cfg: ExperimentConfig, loaded: LoadedConfig
) -> tuple[Dataset[Any], Dataset[Any], Dataset[Any], dict[str, Any]]:
    if cfg.data.dataset_name == "pcam":
        ensure_pcam(loaded.resolved_data_dir, download_requested=cfg.data.download)
    else:
        logger.warning(SYNTHETIC_DATA_WARNING)

    mean, std = _stats_for_architecture(cfg, loaded)
    normalization: dict[str, Any] = (
        {"mean": list(mean), "std": list(std)}
        if mean is not None and std is not None
        else {"scheme": "imagenet"}
    )

    train_transform = build_transform(
        "train", cfg.model.architecture, cfg.data.image_size, mean, std
    )
    val_transform = build_transform("val", cfg.model.architecture, cfg.data.image_size, mean, std)
    test_transform = build_transform("test", cfg.model.architecture, cfg.data.image_size, mean, std)

    train_ds = _build_split_dataset(cfg, loaded, "train", train_transform)
    val_ds = _build_split_dataset(cfg, loaded, "val", val_transform)
    test_ds = _build_split_dataset(cfg, loaded, "test", test_transform)
    return train_ds, val_ds, test_ds, normalization


def _build_loaders(
    cfg: ExperimentConfig, train_ds: Dataset[Any], val_ds: Dataset[Any], test_ds: Dataset[Any]
) -> tuple[DataLoader[Any], DataLoader[Any], DataLoader[Any]]:
    common = {
        "num_workers": cfg.data.num_workers,
        "pin_memory": cfg.data.pin_memory,
        "persistent_workers": cfg.data.persistent_workers,
        "prefetch_factor": cfg.data.prefetch_factor,
        "seed": cfg.experiment.seed,
    }
    train_loader = build_loader(train_ds, "train", cfg.training.batch_size, **common)  # type: ignore[arg-type]
    val_loader = build_loader(val_ds, "val", cfg.training.batch_size, **common)  # type: ignore[arg-type]
    test_loader = build_loader(test_ds, "test", cfg.training.batch_size, **common)  # type: ignore[arg-type]
    return train_loader, val_loader, test_loader


def _patch_checkpoint_normalization(path: Path, normalization: dict[str, Any]) -> None:
    payload = load_checkpoint(path)
    payload.normalization = normalization
    save_checkpoint(path, payload)


# --- commands ------------------------------------------------------------------------


def cmd_environment(_args: argparse.Namespace) -> int:
    for key, value in collect_environment_metadata().items():
        print(f"{key}: {value}")
    return 0


def cmd_data_inspect(args: argparse.Namespace) -> int:
    loaded = load_config(args.config, overrides=args.set)
    cfg = loaded.config
    splits: dict[str, SplitReport] = {}
    split_names: tuple[SplitName, ...] = ("train", "val", "test")
    for split in split_names:
        dataset = _build_split_dataset(cfg, loaded, split, transform=T.ToTensor())
        splits[split] = inspect_split(dataset, split, CLASS_NAMES, max_samples=args.max_samples)
    report = build_dataset_report(cfg.data.dataset_name, splits)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = REPO_ROOT / "artifacts" / "dataset_reports" / cfg.data.dataset_name / timestamp
    json_path, md_path = write_dataset_report(report, output_dir)
    print(f"Dataset report written to {json_path} and {md_path}")
    for risk in report.risks:
        print(f"  risk: {risk}")
    return 0


def cmd_data_download(args: argparse.Namespace) -> int:
    loaded = load_config(args.config, overrides=args.set)
    decision = ensure_pcam(loaded.resolved_data_dir, download_requested=args.download)
    print(decision.message)
    if not args.download:
        print(
            f"(pass --download, with {ALLOW_DATA_DOWNLOAD_ENV_VAR}=1 set, to actually fetch PCam)"
        )
    return 0 if decision.status.value in ("preconditions_satisfied", "not_requested") else 1


def cmd_train(args: argparse.Namespace) -> int:
    loaded = load_config(args.config, overrides=args.set)
    cfg = loaded.config

    repro_report = set_seed(cfg.experiment.seed, deterministic=cfg.runtime.deterministic)
    device = resolve_device(cfg.runtime.device)
    env_metadata = collect_environment_metadata()
    logger.info("Device: %s (%s)", device.device, device.device_name)

    experiment_id = _new_experiment_id(cfg.experiment.name)
    experiment_dir = loaded.resolved_output_dir / experiment_id
    experiment_dir.mkdir(parents=True, exist_ok=True)

    _write_yaml(experiment_dir / "resolved_config.yaml", cfg.model_dump(mode="json"))
    (experiment_dir / "environment.json").write_text(
        json.dumps(
            {
                **env_metadata,
                "reproducibility": asdict(repro_report),
                "config_hash": loaded.config_hash,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    registry = ExperimentRegistry(REPO_ROOT / EXPERIMENT_REGISTRY_RELATIVE_PATH)
    dataset_mode = "synthetic" if cfg.data.dataset_name == "synthetic" else "pcam"
    started_at = _utc_now_iso()

    try:
        train_ds, val_ds, test_ds, normalization = _build_datasets(cfg, loaded)
        train_loader, val_loader, _test_loader = _build_loaders(cfg, train_ds, val_ds, test_ds)

        model, model_metadata = build_model(
            cfg.model.architecture,
            pretrained=cfg.model.pretrained,
            dropout=cfg.model.dropout,
            freeze_backbone=cfg.model.freeze_backbone,
            unfreeze_from_layer=cfg.model.unfreeze_from_layer,
            image_size=cfg.data.image_size,
        )
        logger.info(
            "Model %s: %d total params, %d trainable",
            cfg.model.architecture,
            model_metadata.total_parameters,
            model_metadata.trainable_parameters,
        )

        loss_fn = build_loss()
        optimizer = build_optimizer(
            model, cfg.training.optimizer, cfg.training.learning_rate, cfg.training.weight_decay
        )
        scheduler = build_scheduler(
            optimizer, cfg.training.scheduler, cfg.training.monitored_mode, cfg.training.epochs
        )

        training_result = fit(
            model=model,
            train_loader=train_loader,
            val_loader=val_loader,
            optimizer=optimizer,
            scheduler=scheduler,
            loss_fn=loss_fn,
            device=device,
            epochs=cfg.training.epochs,
            experiment_dir=experiment_dir,
            architecture=cfg.model.architecture,
            model_config=cfg.model.model_dump(mode="json"),
            training_config=cfg.training.model_dump(mode="json"),
            class_names=CLASS_NAMES,
            threshold=cfg.evaluation.default_threshold,
            monitored_metric=cfg.training.monitored_metric,
            monitored_mode=cfg.training.monitored_mode,
            early_stopping_patience=cfg.training.early_stopping_patience,
            mixed_precision=cfg.training.mixed_precision,
            grad_clip_norm=cfg.training.gradient_clip_norm,
            accumulation_steps=cfg.training.accumulation_steps,
            tensorboard=cfg.logging.tensorboard,
            show_progress=args.progress,
        )
        _patch_checkpoint_normalization(training_result.best_checkpoint_path, normalization)
        _patch_checkpoint_normalization(training_result.last_checkpoint_path, normalization)

        registry.append(
            ExperimentRecord(
                experiment_id=experiment_id,
                name=cfg.experiment.name,
                architecture=cfg.model.architecture,
                dataset=cfg.data.dataset_name,
                dataset_mode=dataset_mode,  # type: ignore[arg-type]
                status="completed",
                started_at=started_at,
                completed_at=_utc_now_iso(),
                best_epoch=training_result.best_epoch,
                best_validation_metric=training_result.best_metric,
                selected_threshold=cfg.evaluation.default_threshold,
                test_metrics_available=False,
                artifact_path=str(experiment_dir),
                config_hash=loaded.config_hash,
                git_commit=env_metadata.get("git_commit"),
            )
        )
    except Exception:
        logger.exception("Training failed for experiment %s", experiment_id)
        try:
            registry.append(
                ExperimentRecord(
                    experiment_id=experiment_id,
                    name=cfg.experiment.name,
                    architecture=cfg.model.architecture,
                    dataset=cfg.data.dataset_name,
                    dataset_mode=dataset_mode,  # type: ignore[arg-type]
                    status="failed",
                    started_at=started_at,
                    completed_at=_utc_now_iso(),
                    artifact_path=str(experiment_dir),
                    config_hash=loaded.config_hash,
                    git_commit=env_metadata.get("git_commit"),
                )
            )
        except Exception:
            logger.exception("Could not record the failed experiment %s either", experiment_id)
        return 1

    if cfg.data.dataset_name == "synthetic":
        print(SYNTHETIC_DATA_WARNING)
    print(f"Training complete. experiment_id={experiment_id}")
    print(f"Artifacts: {experiment_dir}")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    experiment_dir = _experiment_dir_for_id(args.experiment_id)
    loaded = _load_experiment_config(experiment_dir)
    cfg = loaded.config
    device = resolve_device(cfg.runtime.device)

    _train_ds, val_ds, test_ds, _normalization = _build_datasets(cfg, loaded)
    _train_loader, val_loader, test_loader = _build_loaders(cfg, _train_ds, val_ds, test_ds)

    model, _metadata = build_model(
        cfg.model.architecture,
        pretrained=False,
        dropout=cfg.model.dropout,
        image_size=cfg.data.image_size,
    )
    checkpoint_path = experiment_dir / "checkpoints" / "best.pt"
    payload = load_checkpoint(checkpoint_path, expected_architecture=cfg.model.architecture)
    model.load_state_dict(payload.model_state_dict)
    model.to(device.device)

    result = run_full_evaluation(
        model=model,
        val_loader=val_loader,
        test_loader=test_loader,
        loss_fn=build_loss(),
        device=device,
        output_dir=experiment_dir,
        class_names=CLASS_NAMES,
        threshold_strategy=cfg.evaluation.threshold_strategy,
        default_threshold=cfg.evaluation.default_threshold,
        target_sensitivity=cfg.evaluation.target_sensitivity,
        calibrate=cfg.evaluation.calibration,
        bootstrap_samples=cfg.evaluation.bootstrap_samples,
        confidence_level=cfg.evaluation.confidence_level,
        seed=cfg.experiment.seed,
    )
    if cfg.data.dataset_name == "synthetic":
        print(SYNTHETIC_DATA_WARNING)
    print(f"Evaluation complete. Report: {result.report_path}")
    print(f"Predictions: {result.predictions_path}")
    print(f"Metrics: {result.metrics_path}")
    return 0


def _index_from_sample_id(sample_id: str) -> int:
    return int(str(sample_id).rsplit("_", 1)[1])


def _pick_explain_indices(
    experiment_dir: Path, dataset_size: int, num_samples: int
) -> list[tuple[int, str]]:
    predictions_path = experiment_dir / "predictions" / "test_predictions.csv"
    if not predictions_path.is_file():
        return [(i, "sample") for i in range(min(num_samples, dataset_size))]

    df = pd.read_csv(predictions_path)
    picks: list[tuple[int, str]] = []
    categories = {
        "true_positive": (df["true_label"] == 1) & (df["predicted_label"] == 1),
        "true_negative": (df["true_label"] == 0) & (df["predicted_label"] == 0),
        "false_positive": (df["true_label"] == 0) & (df["predicted_label"] == 1),
        "false_negative": (df["true_label"] == 1) & (df["predicted_label"] == 0),
    }
    for name, mask in categories.items():
        subset = df.loc[mask]
        if len(subset):
            picks.append((_index_from_sample_id(subset.iloc[0]["sample_id"]), name))

    if len(df):
        prob_col = (
            "calibrated_probability"
            if "calibrated_probability" in df.columns and df["calibrated_probability"].notna().any()
            else "uncalibrated_probability"
        )
        threshold = float(df["threshold"].iloc[0])
        near_threshold = df.loc[(df[prob_col] - threshold).abs() < 0.1]
        if len(near_threshold):
            picks.append((_index_from_sample_id(near_threshold.iloc[0]["sample_id"]), "uncertain"))

    return picks[:num_samples] if num_samples else picks


def cmd_explain(args: argparse.Namespace) -> int:
    experiment_dir = _experiment_dir_for_id(args.experiment_id)
    loaded = _load_experiment_config(experiment_dir)
    cfg = loaded.config
    device = resolve_device(cfg.runtime.device)

    mean, std = _stats_for_architecture(cfg, loaded)
    model_transform = build_transform(
        "test", cfg.model.architecture, cfg.data.image_size, mean, std
    )
    display_transform = T.Compose(
        [T.Resize((cfg.data.image_size, cfg.data.image_size)), T.ToTensor()]
    )

    test_model_ds = _build_split_dataset(cfg, loaded, "test", model_transform)
    test_display_ds = _build_split_dataset(cfg, loaded, "test", display_transform)

    model, _metadata = build_model(
        cfg.model.architecture,
        pretrained=False,
        dropout=cfg.model.dropout,
        image_size=cfg.data.image_size,
    )
    payload = load_checkpoint(
        experiment_dir / "checkpoints" / "best.pt", expected_architecture=cfg.model.architecture
    )
    model.load_state_dict(payload.model_state_dict)
    model.to(device.device)
    model.eval()

    target_layer = get_target_layer(model, cfg.model.architecture)
    indices = _pick_explain_indices(experiment_dir, len(test_model_ds), args.num_samples)  # type: ignore[arg-type]

    gradcam_dir = experiment_dir / "gradcam"
    gradcam_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    with GradCAM(model, target_layer) as cam:
        for index, category in indices:
            input_tensor, _label, sample_id = test_model_ds[index]
            display_tensor, _, _ = test_display_ds[index]
            heatmap = cam.generate(input_tensor.unsqueeze(0).to(device.device))
            display_image = (display_tensor.permute(1, 2, 0).numpy() * 255).astype("uint8")
            output_path = save_overlay(
                display_image, heatmap, gradcam_dir / f"{category}_{sample_id}.png"
            )
            generated.append(output_path)

    (gradcam_dir / "DISCLAIMER.txt").write_text(GRADCAM_DISCLAIMER, encoding="utf-8")
    print(f"Generated {len(generated)} Grad-CAM overlay(s) in {gradcam_dir}")
    return 0 if generated else 1


def cmd_register(args: argparse.Namespace) -> int:
    experiment_dir = _experiment_dir_for_id(args.experiment_id)
    loaded = _load_experiment_config(experiment_dir)
    cfg = loaded.config

    checkpoint_path = experiment_dir / "checkpoints" / "best.pt"
    payload = load_checkpoint(checkpoint_path, expected_architecture=cfg.model.architecture)
    checkpoint_hash = sha256_file(checkpoint_path)

    metrics_path = experiment_dir / "metrics" / "metrics.json"
    if not metrics_path.is_file():
        print(
            f"No metrics.json found at {metrics_path} - run `evaluate` for this experiment first.",
            file=sys.stderr,
        )
        return 1
    metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))

    is_synthetic = cfg.data.dataset_name == "synthetic"
    model_name = args.model_name or cfg.experiment.name
    manifest = ModelManifest(
        model_id=f"{model_name}:{args.version}",
        model_name=model_name,
        model_version=args.version,
        architecture=cfg.model.architecture,
        checkpoint_sha256=checkpoint_hash,
        dataset_name=cfg.data.dataset_name,
        dataset_version="synthetic-v1" if is_synthetic else "pcam-v1",
        dataset_mode="synthetic" if is_synthetic else "pcam",
        input_height=cfg.data.image_size,
        input_width=cfg.data.image_size,
        input_channels=3,
        class_names=CLASS_NAMES,
        positive_class=CLASS_NAMES[1],
        normalization=payload.normalization,
        threshold=metrics_payload["threshold"],
        review_policy=None,
        calibration={"temperature": metrics_payload["temperature"]}
        if metrics_payload.get("temperature")
        else None,
        validation_metrics=metrics_payload["validation_metrics"],
        test_metrics=metrics_payload["test_metrics"],
        git_commit=payload.git_commit,
        created_at=_utc_now_iso(),
        eligible_for_demo=not is_synthetic,
        synthetic_only=is_synthetic,
    )

    registry = ModelRegistry(REPO_ROOT / "artifacts" / "model_registry")
    registry.register(checkpoint_path, manifest)

    target_dir = registry.model_dir(model_name, args.version)
    model_card = _render_model_card(manifest)
    build_bundle(checkpoint_path, manifest, target_dir, model_card)

    if is_synthetic:
        print(SYNTHETIC_DATA_WARNING)
    print(f"Registered {model_name}:{args.version} -> {target_dir}")
    return 0


def _render_model_card(manifest: ModelManifest) -> str:
    from medrisk_ml.constants import MEDICAL_DISCLAIMER

    lines = [
        f"# Model card: {manifest.model_name} v{manifest.model_version}",
        "",
        f"- Architecture: {manifest.architecture}",
        f"- Dataset: {manifest.dataset_name} ({manifest.dataset_mode}, {manifest.dataset_version})",
        f"- Input: {manifest.input_channels}x{manifest.input_height}x{manifest.input_width}",
        f"- Classes: {manifest.class_names} (positive={manifest.positive_class})",
        f"- Threshold: {manifest.threshold}",
        f"- Calibration: {manifest.calibration}",
        f"- Eligible for demo: {manifest.eligible_for_demo}",
        f"- Synthetic only: {manifest.synthetic_only}",
        f"- Validation metrics: {manifest.validation_metrics}",
        f"- Test metrics: {manifest.test_metrics}",
        f"- Git commit: {manifest.git_commit}",
        f"- Created at: {manifest.created_at}",
        "",
        "See docs/model-card-template.md for the full template this summarizes.",
        "",
        MEDICAL_DISCLAIMER,
    ]
    return "\n".join(lines)


def cmd_verify_bundle(args: argparse.Namespace) -> int:
    if ":" not in args.model_id:
        print("--model-id must be in the form <model_name>:<model_version>", file=sys.stderr)
        return 1
    model_name, version = args.model_id.split(":", 1)
    bundle_dir = REPO_ROOT / "artifacts" / "model_registry" / model_name / version
    result = verify_bundle(bundle_dir)
    if result.valid:
        print(f"Bundle OK: {bundle_dir} (smoke_inference_ok={result.smoke_inference_ok})")
        return 0
    print(f"Bundle INVALID: {bundle_dir}", file=sys.stderr)
    for error in result.errors:
        print(f"  - {error}", file=sys.stderr)
    return 1


# --- argument parsing -----------------------------------------------------------------


def _add_config_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config", required=True, type=Path, help="Path to a YAML experiment config"
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Override a config value, e.g. training.epochs=2",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="medrisk_ml", description="MedRisk AI Phase 2 ML pipeline"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "environment", help="Print interpreter/library/hardware info"
    ).set_defaults(func=cmd_environment)

    data_parser = subparsers.add_parser("data", help="Dataset inspection/download")
    data_subparsers = data_parser.add_subparsers(dest="data_command", required=True)

    inspect_parser = data_subparsers.add_parser(
        "inspect", help="Inspect dataset splits and write a report"
    )
    _add_config_args(inspect_parser)
    inspect_parser.add_argument("--max-samples", type=int, default=None)
    inspect_parser.set_defaults(func=cmd_data_inspect)

    download_parser = data_subparsers.add_parser("download", help="Download real PCam (gated)")
    _add_config_args(download_parser)
    download_parser.add_argument(
        "--download", action="store_true", help="Actually attempt the download"
    )
    download_parser.set_defaults(func=cmd_data_download)

    train_parser = subparsers.add_parser("train", help="Train a model from a config")
    _add_config_args(train_parser)
    train_parser.add_argument("--progress", action="store_true", help="Show tqdm progress bars")
    train_parser.set_defaults(func=cmd_train)

    evaluate_parser = subparsers.add_parser(
        "evaluate", help="Run the final evaluation for a trained experiment"
    )
    evaluate_parser.add_argument("--experiment-id", required=True)
    evaluate_parser.set_defaults(func=cmd_evaluate)

    explain_parser = subparsers.add_parser(
        "explain", help="Generate Grad-CAM overlays for a trained experiment"
    )
    explain_parser.add_argument("--experiment-id", required=True)
    explain_parser.add_argument("--num-samples", type=int, default=8)
    explain_parser.set_defaults(func=cmd_explain)

    register_parser = subparsers.add_parser(
        "register", help="Register a trained+evaluated model into the model registry"
    )
    register_parser.add_argument("--experiment-id", required=True)
    register_parser.add_argument("--version", required=True)
    register_parser.add_argument("--model-name", default=None)
    register_parser.set_defaults(func=cmd_register)

    verify_parser = subparsers.add_parser("verify-bundle", help="Verify a registered model bundle")
    verify_parser.add_argument("--model-id", required=True, help="<model_name>:<model_version>")
    verify_parser.set_defaults(func=cmd_verify_bundle)

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.getLogger("medrisk_ml").setLevel(logging.INFO)
    parser = build_parser()
    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())

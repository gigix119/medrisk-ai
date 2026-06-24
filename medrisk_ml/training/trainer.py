"""Trainer: orchestrates the full fit loop plus experiment directory/checkpoint/history I/O.

Creates `artifacts/experiments/<experiment_id>/{checkpoints,logs}/`, runs train/validation
epochs, drives early stopping and the scheduler, writes `best.pt`/`last.pt`, and saves
training history as JSON + CSV. Test data never appears anywhere in this module.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import torch
from torch import nn
from torch.utils.data import DataLoader

from medrisk_ml.evaluation.metrics import compute_binary_metrics, sigmoid
from medrisk_ml.training.checkpointing import CheckpointPayload, save_checkpoint
from medrisk_ml.training.early_stopping import EarlyStopping
from medrisk_ml.training.engine import evaluate, train_one_epoch
from medrisk_ml.training.scheduler import SchedulerWrapper, current_lr
from medrisk_ml.types import MonitorMode
from medrisk_ml.utils.device import ResolvedDevice
from medrisk_ml.utils.logging import get_logger
from medrisk_ml.utils.reproducibility import get_git_commit

logger = get_logger(__name__)


@dataclass
class TrainingResult:
    experiment_dir: Path
    best_checkpoint_path: Path
    last_checkpoint_path: Path
    history: list[dict[str, Any]]
    best_epoch: int
    best_metric: float
    stopped_early: bool
    final_epoch: int


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def fit(
    *,
    model: nn.Module,
    train_loader: DataLoader[Any],
    val_loader: DataLoader[Any],
    optimizer: torch.optim.Optimizer,
    scheduler: SchedulerWrapper,
    loss_fn: nn.Module,
    device: ResolvedDevice,
    epochs: int,
    experiment_dir: Path,
    architecture: str,
    model_config: dict[str, Any],
    training_config: dict[str, Any],
    class_names: tuple[str, str],
    threshold: float = 0.5,
    monitored_metric: str = "roc_auc",
    monitored_mode: MonitorMode = "max",
    early_stopping_patience: int = 5,
    mixed_precision: bool = False,
    grad_clip_norm: float | None = None,
    accumulation_steps: int = 1,
    tensorboard: bool = True,
    show_progress: bool = False,
) -> TrainingResult:
    model.to(device.device)
    checkpoints_dir = experiment_dir / "checkpoints"
    logs_dir = experiment_dir / "logs"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    writer = None
    if tensorboard:
        from torch.utils.tensorboard import SummaryWriter

        writer = SummaryWriter(log_dir=str(logs_dir))

    early_stopping = EarlyStopping(patience=early_stopping_patience, mode=monitored_mode)

    history: list[dict[str, Any]] = []
    best_checkpoint_path = checkpoints_dir / "best.pt"
    last_checkpoint_path = checkpoints_dir / "last.pt"
    global_step = 0
    stopped_early = False
    final_epoch = 0

    for epoch in range(1, epochs + 1):
        final_epoch = epoch
        train_result = train_one_epoch(
            model,
            train_loader,
            optimizer,
            loss_fn,
            device,
            mixed_precision=mixed_precision,
            grad_clip_norm=grad_clip_norm,
            accumulation_steps=accumulation_steps,
            show_progress=show_progress,
        )
        global_step += len(train_loader)
        val_result = evaluate(model, val_loader, loss_fn, device, show_progress=show_progress)

        train_metrics = compute_binary_metrics(
            train_result.labels, sigmoid(train_result.logits), threshold
        )
        val_metrics = compute_binary_metrics(
            val_result.labels, sigmoid(val_result.logits), threshold
        )

        monitored_value = val_metrics.get(monitored_metric)
        if monitored_value is None or _is_nan(monitored_value):
            # Fall back to validation loss (always defined) if the chosen metric is
            # undefined this epoch (e.g. ROC-AUC with a one-class validation batch).
            monitored_value = -val_result.loss if monitored_mode == "max" else val_result.loss
        monitored_value = float(monitored_value)

        lr = current_lr(optimizer)
        epoch_record: dict[str, Any] = {
            "epoch": epoch,
            "train_loss": train_result.loss,
            "val_loss": val_result.loss,
            "learning_rate": lr,
            "duration_seconds": round(
                train_result.duration_seconds + val_result.duration_seconds, 4
            ),
            "skipped_batches": train_result.skipped_batches,
            f"train_{monitored_metric}": train_metrics.get(monitored_metric),
            f"val_{monitored_metric}": val_metrics.get(monitored_metric),
        }
        history.append(epoch_record)
        logger.info(
            "epoch=%d train_loss=%.4f val_loss=%.4f val_%s=%.4f lr=%.2e",
            epoch,
            train_result.loss,
            val_result.loss,
            monitored_metric,
            monitored_value,
            lr,
        )

        if writer is not None:
            writer.add_scalar("loss/train", train_result.loss, epoch)
            writer.add_scalar("loss/val", val_result.loss, epoch)
            writer.add_scalar("lr", lr, epoch)
            for key, value in val_metrics.items():
                if isinstance(value, int | float) and not math.isnan(value):
                    writer.add_scalar(f"val/{key}", value, epoch)

        should_stop = early_stopping.step(monitored_value, epoch)

        payload = CheckpointPayload(
            model_state_dict=model.state_dict(),
            optimizer_state_dict=optimizer.state_dict(),
            scheduler_state_dict=scheduler.state_dict(),
            epoch=epoch,
            global_step=global_step,
            best_metric=early_stopping.best_value,
            architecture=architecture,
            model_config=model_config,
            training_config=training_config,
            class_names=class_names,
            normalization={},
            threshold=threshold,
            calibration_metadata=None,
            git_commit=get_git_commit(),
            created_at=_utc_now_iso(),
        )
        save_checkpoint(last_checkpoint_path, payload)
        if early_stopping.best_epoch == epoch:
            save_checkpoint(best_checkpoint_path, payload)

        scheduler.step(monitored_value if scheduler.name == "reduce_on_plateau" else None)

        if should_stop:
            stopped_early = True
            logger.info(
                "Early stopping triggered at epoch %d (best epoch %d)",
                epoch,
                early_stopping.best_epoch,
            )
            break

    if writer is not None:
        writer.close()

    _write_history(experiment_dir, history)

    return TrainingResult(
        experiment_dir=experiment_dir,
        best_checkpoint_path=best_checkpoint_path,
        last_checkpoint_path=last_checkpoint_path,
        history=history,
        best_epoch=early_stopping.best_epoch,
        best_metric=early_stopping.best_value,
        stopped_early=stopped_early,
        final_epoch=final_epoch,
    )


def _is_nan(value: Any) -> bool:
    return isinstance(value, float) and math.isnan(value)


def _write_history(experiment_dir: Path, history: list[dict[str, Any]]) -> None:
    json_path = experiment_dir / "training_history.json"
    csv_path = experiment_dir / "training_history.csv"
    json_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    if not history:
        csv_path.write_text("", encoding="utf-8")
        return
    fieldnames = list(history[0].keys())
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(history)

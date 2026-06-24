"""Core train/validation epoch logic - the one place that runs a model over a loader.

Computes epoch-level metrics from ALL collected predictions, not an average of per-batch
metrics (averaging per-batch accuracy/AUC across batches of different composition would be
mathematically wrong for ranking metrics like ROC-AUC/PR-AUC, and subtly wrong even for
accuracy when the last batch is a different size).
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from tqdm import tqdm

from medrisk_ml.utils.device import ResolvedDevice
from medrisk_ml.utils.logging import get_logger
from medrisk_ml.utils.timing import timer

logger = get_logger(__name__)


@dataclass
class EpochResult:
    loss: float
    logits: np.ndarray
    labels: np.ndarray
    sample_ids: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    skipped_batches: int = 0


def _forward_logits(model: nn.Module, images: torch.Tensor) -> torch.Tensor:
    raw: torch.Tensor = model(images)
    return raw.squeeze(-1)


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader[tuple[torch.Tensor, torch.Tensor, list[str]]],
    optimizer: torch.optim.Optimizer,
    loss_fn: nn.Module,
    device: ResolvedDevice,
    mixed_precision: bool = False,
    grad_clip_norm: float | None = None,
    accumulation_steps: int = 1,
    max_consecutive_non_finite: int = 5,
    show_progress: bool = False,
) -> EpochResult:
    model.train()
    amp_enabled = mixed_precision and device.supports_amp
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)

    all_logits: list[np.ndarray] = []
    all_labels: list[np.ndarray] = []
    all_ids: list[str] = []
    total_loss = 0.0
    num_batches = 0
    skipped = 0
    consecutive_non_finite = 0

    optimizer.zero_grad(set_to_none=True)
    iterable = tqdm(loader, disable=not show_progress, desc="train")
    with timer() as elapsed:
        for step, (images, labels, sample_ids) in enumerate(iterable):
            images = images.to(device.device, non_blocking=True)
            labels_float = labels.to(device.device, non_blocking=True).float()

            autocast_ctx = (
                torch.autocast(device_type="cuda") if amp_enabled else contextlib.nullcontext()
            )
            with autocast_ctx:
                logits = _forward_logits(model, images)
                loss = loss_fn(logits, labels_float) / accumulation_steps

            if not torch.isfinite(loss):
                consecutive_non_finite += 1
                skipped += 1
                logger.warning(
                    "Non-finite loss at batch %d, skipping (consecutive=%d)",
                    step,
                    consecutive_non_finite,
                )
                optimizer.zero_grad(set_to_none=True)
                if consecutive_non_finite >= max_consecutive_non_finite:
                    raise RuntimeError(
                        f"{consecutive_non_finite} consecutive non-finite losses - aborting training"
                    )
                continue
            consecutive_non_finite = 0

            scaler.scale(loss).backward()

            if (step + 1) % accumulation_steps == 0:
                if grad_clip_norm is not None:
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip_norm)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)

            total_loss += loss.item() * accumulation_steps
            num_batches += 1
            all_logits.append(logits.detach().float().cpu().numpy())
            all_labels.append(labels_float.detach().cpu().numpy())
            all_ids.extend(sample_ids)

    mean_loss = total_loss / num_batches if num_batches else float("nan")
    return EpochResult(
        loss=mean_loss,
        logits=np.concatenate(all_logits) if all_logits else np.array([]),
        labels=np.concatenate(all_labels) if all_labels else np.array([]),
        sample_ids=all_ids,
        duration_seconds=elapsed.seconds,
        skipped_batches=skipped,
    )


@torch.no_grad()
def evaluate(
    model: nn.Module,
    loader: DataLoader[tuple[torch.Tensor, torch.Tensor, list[str]]],
    loss_fn: nn.Module,
    device: ResolvedDevice,
    show_progress: bool = False,
) -> EpochResult:
    model.eval()
    all_logits: list[np.ndarray] = []
    all_labels: list[np.ndarray] = []
    all_ids: list[str] = []
    total_loss = 0.0
    num_batches = 0

    iterable = tqdm(loader, disable=not show_progress, desc="eval")
    with timer() as elapsed:
        for images, labels, sample_ids in iterable:
            images = images.to(device.device, non_blocking=True)
            labels_float = labels.to(device.device, non_blocking=True).float()
            logits = _forward_logits(model, images)
            loss = loss_fn(logits, labels_float)
            total_loss += loss.item()
            num_batches += 1
            all_logits.append(logits.detach().float().cpu().numpy())
            all_labels.append(labels_float.detach().cpu().numpy())
            all_ids.extend(sample_ids)

    mean_loss = total_loss / num_batches if num_batches else float("nan")
    return EpochResult(
        loss=mean_loss,
        logits=np.concatenate(all_logits) if all_logits else np.array([]),
        labels=np.concatenate(all_labels) if all_labels else np.array([]),
        sample_ids=all_ids,
        duration_seconds=elapsed.seconds,
    )

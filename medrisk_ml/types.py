"""Shared type aliases and small value objects used across the ML package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ArchitectureName = Literal["baseline_cnn", "resnet18"]
SplitName = Literal["train", "val", "test"]
DatasetName = Literal["pcam", "synthetic"]
ThresholdStrategy = Literal["fixed", "youden_j", "max_f1", "target_sensitivity"]
OptimizerName = Literal["adamw", "sgd"]
SchedulerName = Literal["reduce_on_plateau", "cosine", "none"]
MonitorMode = Literal["min", "max"]
DeviceRequest = Literal["auto", "cuda", "mps", "cpu"]

MetricsDict = dict[str, float | int | None]


@dataclass(frozen=True)
class PredictionRecord:
    """One row of the per-sample prediction table saved by the evaluator."""

    sample_id: str
    split: SplitName
    true_label: int
    logit: float
    uncalibrated_probability: float
    calibrated_probability: float | None
    predicted_label: int
    threshold: float
    correct: bool

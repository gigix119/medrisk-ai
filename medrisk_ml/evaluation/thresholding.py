"""Threshold-selection strategies, fit on validation data only.

`split_name` must not be "test" - passing it raises `SplitLeakageError`, a code-level
guard against ever using the test set to pick a decision threshold.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import precision_recall_curve, roc_curve

from medrisk_ml.evaluation.metrics import compute_binary_metrics
from medrisk_ml.types import MetricsDict, ThresholdStrategy


class SplitLeakageError(RuntimeError):
    """Raised when threshold fitting is attempted against the test split."""


@dataclass(frozen=True)
class ThresholdResult:
    strategy: ThresholdStrategy
    threshold: float
    validation_metrics: MetricsDict
    target_sensitivity: float | None = None
    target_achieved: bool | None = None


def select_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    strategy: ThresholdStrategy,
    split_name: str,
    default_threshold: float = 0.5,
    target_sensitivity: float | None = None,
) -> ThresholdResult:
    if split_name == "test":
        raise SplitLeakageError(
            "Threshold selection must use the validation split, not the test split"
        )

    if strategy == "target_sensitivity":
        if target_sensitivity is None:
            raise ValueError("target_sensitivity strategy requires a target_sensitivity value")
        threshold, achieved = _target_sensitivity(y_true, y_prob, target_sensitivity)
        metrics = compute_binary_metrics(y_true, y_prob, threshold)
        return ThresholdResult(
            strategy=strategy,
            threshold=threshold,
            validation_metrics=metrics,
            target_sensitivity=target_sensitivity,
            target_achieved=achieved,
        )

    if strategy == "fixed":
        threshold = default_threshold
    elif strategy == "youden_j":
        threshold = _youden_j(y_true, y_prob)
    elif strategy == "max_f1":
        threshold = _max_f1(y_true, y_prob)
    else:
        raise ValueError(f"Unknown threshold strategy: {strategy!r}")

    metrics = compute_binary_metrics(y_true, y_prob, threshold)
    return ThresholdResult(strategy=strategy, threshold=threshold, validation_metrics=metrics)


def _youden_j(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return 0.5
    fpr, tpr, thresholds = roc_curve(y_true, y_prob)
    j_scores = tpr - fpr
    best_index = int(np.argmax(j_scores))
    return float(np.clip(thresholds[best_index], 0.0, 1.0))


def _max_f1(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return 0.5
    precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
    if len(thresholds) == 0:
        return 0.5
    # precision_recall_curve appends a synthetic (precision=1, recall=0) point with no
    # corresponding threshold - drop it so the arrays line up with `thresholds`.
    precision = precision[:-1]
    recall = recall[:-1]
    denom = precision + recall
    f1_scores = np.divide(2 * precision * recall, denom, out=np.zeros_like(denom), where=denom > 0)
    best_index = int(np.argmax(f1_scores))
    return float(thresholds[best_index])


def _target_sensitivity(
    y_true: np.ndarray, y_prob: np.ndarray, target: float
) -> tuple[float, bool]:
    if len(np.unique(y_true)) < 2:
        return 0.5, False
    _fpr, tpr, thresholds = roc_curve(y_true, y_prob)
    candidates = np.where(tpr >= target)[0]
    if candidates.size == 0:
        # Target sensitivity is unreachable on this data - report the best achievable instead.
        best_index = int(np.argmax(tpr))
        return float(np.clip(thresholds[best_index], 0.0, 1.0)), False
    # Among thresholds achieving >= target sensitivity, prefer the highest (most specific).
    best_index = int(candidates[np.argmax(thresholds[candidates])])
    return float(np.clip(thresholds[best_index], 0.0, 1.0)), True

"""Binary classification metrics, computed primarily from scratch on numpy arrays.

`y_true` are 0/1 ints, `y_prob` are probabilities in [0,1] (apply `sigmoid()` to raw model
logits first). Metrics that are mathematically undefined for a given confusion matrix
(e.g. precision when there are no positive predictions at all, or ROC-AUC when only one
class is present) are reported as `float("nan")`, never silently replaced by 0 or 1 - see
docs/evaluation.md for the full undefined-metric policy and formulas.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from medrisk_ml.types import MetricsDict

_SCALAR_METRIC_KEYS = (
    "accuracy",
    "balanced_accuracy",
    "precision",
    "recall",
    "sensitivity",
    "specificity",
    "f1",
    "roc_auc",
    "pr_auc",
    "brier_score",
)
_COUNT_KEYS = (
    "true_positive",
    "true_negative",
    "false_positive",
    "false_negative",
    "sample_count",
    "positive_count",
    "negative_count",
)


def sigmoid(logits: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid (clips logits to +-30, well beyond where it saturates)."""
    clipped = np.clip(logits, -30.0, 30.0)
    result: np.ndarray = 1.0 / (1.0 + np.exp(-clipped))
    return result


@dataclass(frozen=True)
class ConfusionCounts:
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int

    @property
    def sample_count(self) -> int:
        return self.true_positive + self.true_negative + self.false_positive + self.false_negative

    @property
    def positive_count(self) -> int:
        return self.true_positive + self.false_negative

    @property
    def negative_count(self) -> int:
        return self.true_negative + self.false_positive


def confusion_counts(y_true: np.ndarray, y_pred: np.ndarray) -> ConfusionCounts:
    true_arr = np.asarray(y_true).astype(int)
    pred_arr = np.asarray(y_pred).astype(int)
    tp = int(np.sum((true_arr == 1) & (pred_arr == 1)))
    tn = int(np.sum((true_arr == 0) & (pred_arr == 0)))
    fp = int(np.sum((true_arr == 0) & (pred_arr == 1)))
    fn = int(np.sum((true_arr == 1) & (pred_arr == 0)))
    return ConfusionCounts(true_positive=tp, true_negative=tn, false_positive=fp, false_negative=fn)


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return float("nan")
    return numerator / denominator


def compute_binary_metrics(
    y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.5
) -> MetricsDict:
    """All Phase 2 binary metrics for one (y_true, y_prob) pair at a fixed `threshold`."""
    true_arr = np.asarray(y_true).astype(int)
    prob_arr = np.asarray(y_prob).astype(float)
    if true_arr.shape[0] == 0:
        return _empty_metrics()

    y_pred = (prob_arr >= threshold).astype(int)
    counts = confusion_counts(true_arr, y_pred)

    sensitivity = _safe_div(counts.true_positive, counts.positive_count)
    specificity = _safe_div(counts.true_negative, counts.negative_count)
    precision = _safe_div(counts.true_positive, counts.true_positive + counts.false_positive)
    recall = sensitivity
    accuracy = _safe_div(counts.true_positive + counts.true_negative, counts.sample_count)
    balanced_accuracy = (
        float("nan")
        if np.isnan(sensitivity) or np.isnan(specificity)
        else (sensitivity + specificity) / 2.0
    )
    f1 = (
        float("nan")
        if np.isnan(precision) or np.isnan(recall) or (precision + recall) == 0
        else 2 * precision * recall / (precision + recall)
    )

    classes_present = np.unique(true_arr)
    if classes_present.size < 2:
        roc_auc = float("nan")
        pr_auc = float("nan")
    else:
        roc_auc = float(roc_auc_score(true_arr, prob_arr))
        pr_auc = float(average_precision_score(true_arr, prob_arr))

    brier = float(np.mean((prob_arr - true_arr) ** 2))

    metrics: MetricsDict = {
        "accuracy": accuracy,
        "balanced_accuracy": balanced_accuracy,
        "precision": precision,
        "recall": recall,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "f1": f1,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "brier_score": brier,
        "true_positive": counts.true_positive,
        "true_negative": counts.true_negative,
        "false_positive": counts.false_positive,
        "false_negative": counts.false_negative,
        "sample_count": counts.sample_count,
        "positive_count": counts.positive_count,
        "negative_count": counts.negative_count,
    }
    return metrics


def _empty_metrics() -> MetricsDict:
    result: MetricsDict = {key: float("nan") for key in _SCALAR_METRIC_KEYS}
    for key in _COUNT_KEYS:
        result[key] = 0
    return result

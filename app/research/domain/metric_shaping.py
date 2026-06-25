"""Converts a raw numeric metrics mapping (e.g.
`medrisk_ml.evaluation.metrics.MetricsDict`, which reports mathematically undefined values as
`float("nan")`) into the structured, JSON-safe shape the research platform persists and
serves: `{"name", "value", "status", "reason"}`.

NaN is never written to a JSONB column (it is not valid JSON), and this is the one and only
place that conversion happens - so "undefined" can never silently become a stored `0.0`
anywhere downstream, and the live API never needs to know what produced the number in the
first place.
"""

from __future__ import annotations

import math
from typing import Any

_UNDEFINED_REASONS: dict[str, str] = {
    "roc_auc": "Only one ground-truth class is present in this split.",
    "pr_auc": "Only one ground-truth class is present in this split.",
    "precision": "No positive predictions were made (TP + FP = 0).",
    "recall": "No actual positive samples are present (TP + FN = 0).",
    "sensitivity": "No actual positive samples are present (TP + FN = 0).",
    "specificity": "No actual negative samples are present (TN + FP = 0).",
    "balanced_accuracy": "Sensitivity or specificity is undefined for this split.",
    "f1": "Precision and recall are both zero or undefined for this split.",
}

_DEFAULT_UNDEFINED_REASON = "This metric is mathematically undefined for this split."

SCALAR_METRIC_NAMES: tuple[str, ...] = (
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

COUNT_FIELD_NAMES: tuple[str, ...] = (
    "true_positive",
    "true_negative",
    "false_positive",
    "false_negative",
    "sample_count",
    "positive_count",
    "negative_count",
)


def shape_metric_result(name: str, value: Any) -> dict[str, Any]:
    """One `{"name", "value", "status", "reason"}` entry - never a raw NaN."""
    if isinstance(value, float) and math.isnan(value):
        return {
            "name": name,
            "value": None,
            "status": "undefined",
            "reason": _UNDEFINED_REASONS.get(name, _DEFAULT_UNDEFINED_REASON),
        }
    if value is None:
        return {"name": name, "value": None, "status": "unavailable", "reason": None}
    return {"name": name, "value": float(value), "status": "ok", "reason": None}


def shape_scalar_metrics(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Shapes only the scalar (possibly-undefined) metrics. Count fields (`true_positive`,
    ...) are always-defined integers and are passed through as-is by the caller."""
    return [shape_metric_result(name, raw[name]) for name in SCALAR_METRIC_NAMES if name in raw]


def extract_counts(raw: dict[str, Any]) -> dict[str, int]:
    return {name: int(raw[name]) for name in COUNT_FIELD_NAMES if name in raw}

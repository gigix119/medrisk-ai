"""Pure unit tests for app.research.domain - no DB, no app.

These cover the scientific-integrity primitives every other Phase 7 module builds on:
split-protocol guards, the forbidden-label check, canonical-JSON hashing, and the NaN-safe
metric shaping that keeps "undefined" from ever silently becoming a stored 0.0.
"""

from __future__ import annotations

import math

import pytest

from app.research.domain.enums import ScientificMaturity
from app.research.domain.hashing import canonical_json, config_hash
from app.research.domain.metric_shaping import (
    extract_counts,
    shape_metric_result,
    shape_scalar_metrics,
)
from app.research.domain.policy import (
    SplitProtocolViolationError,
    assert_not_forbidden_label,
    is_demonstration_only,
    reject_test_split_fitting,
)


def test_reject_test_split_fitting_raises_for_test_split() -> None:
    with pytest.raises(SplitProtocolViolationError):
        reject_test_split_fitting(purpose="Calibration", split_name="test")


def test_reject_test_split_fitting_allows_val_split() -> None:
    reject_test_split_fitting(purpose="Calibration", split_name="val")  # must not raise


def test_assert_not_forbidden_label_raises_case_insensitively() -> None:
    with pytest.raises(ValueError, match="forbidden"):
        assert_not_forbidden_label("Clinically Validated")


def test_assert_not_forbidden_label_allows_real_labels() -> None:
    assert_not_forbidden_label("synthetic demonstration")  # must not raise


def test_is_demonstration_only() -> None:
    assert is_demonstration_only(ScientificMaturity.SYNTHETIC_DEMO) is True
    assert is_demonstration_only(ScientificMaturity.EXPERIMENTAL) is False


def test_config_hash_is_deterministic_and_order_independent() -> None:
    a = {"b": 1, "a": 2}
    b = {"a": 2, "b": 1}
    assert config_hash(a) == config_hash(b)


def test_config_hash_changes_with_content() -> None:
    assert config_hash({"a": 1}) != config_hash({"a": 2})


def test_canonical_json_uses_sorted_keys() -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_shape_metric_result_converts_nan_to_undefined() -> None:
    shaped = shape_metric_result("roc_auc", float("nan"))
    assert shaped == {
        "name": "roc_auc",
        "value": None,
        "status": "undefined",
        "reason": "Only one ground-truth class is present in this split.",
    }


def test_shape_metric_result_uses_default_reason_for_unknown_metric() -> None:
    shaped = shape_metric_result("some_future_metric", float("nan"))
    assert shaped["status"] == "undefined"
    assert shaped["reason"] == "This metric is mathematically undefined for this split."


def test_shape_metric_result_none_is_unavailable_not_undefined() -> None:
    shaped = shape_metric_result("brier_score", None)
    assert shaped["status"] == "unavailable"
    assert shaped["value"] is None


def test_shape_metric_result_ok_value_passes_through() -> None:
    shaped = shape_metric_result("accuracy", 0.875)
    assert shaped == {"name": "accuracy", "value": 0.875, "status": "ok", "reason": None}


def test_shape_scalar_metrics_never_emits_raw_nan() -> None:
    raw = {"accuracy": 1.0, "roc_auc": float("nan"), "true_positive": 16}
    shaped = shape_scalar_metrics(raw)
    values = {entry["name"]: entry for entry in shaped}
    assert "true_positive" not in values  # counts are not scalar metrics
    assert values["roc_auc"]["value"] is None
    assert not any(
        isinstance(entry["value"], float) and math.isnan(entry["value"]) for entry in shaped
    )


def test_extract_counts_only_keeps_known_count_fields() -> None:
    raw = {"true_positive": 1, "false_positive": 0, "accuracy": 1.0, "unrelated": "x"}
    counts = extract_counts(raw)
    assert counts == {"true_positive": 1, "false_positive": 0}

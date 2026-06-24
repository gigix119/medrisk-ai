from __future__ import annotations

import numpy as np
import pytest

from medrisk_ml.evaluation.thresholding import SplitLeakageError, select_threshold

_SEPARABLE_Y_TRUE = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
_SEPARABLE_Y_PROB = np.array([0.05, 0.1, 0.15, 0.2, 0.3, 0.6, 0.7, 0.8, 0.9, 0.95])


def test_fixed_strategy_returns_default_threshold() -> None:
    result = select_threshold(
        _SEPARABLE_Y_TRUE, _SEPARABLE_Y_PROB, "fixed", split_name="val", default_threshold=0.42
    )
    assert result.threshold == 0.42
    assert result.strategy == "fixed"


def test_max_f1_strategy_finds_perfect_separator() -> None:
    result = select_threshold(_SEPARABLE_Y_TRUE, _SEPARABLE_Y_PROB, "max_f1", split_name="val")
    assert 0.3 < result.threshold <= 0.6
    assert result.validation_metrics["f1"] == 1.0


def test_youden_j_strategy_finds_perfect_separator() -> None:
    result = select_threshold(_SEPARABLE_Y_TRUE, _SEPARABLE_Y_PROB, "youden_j", split_name="val")
    assert 0.3 < result.threshold <= 0.6
    assert result.validation_metrics["sensitivity"] == 1.0
    assert result.validation_metrics["specificity"] == 1.0


def test_target_sensitivity_strategy_achieves_target() -> None:
    result = select_threshold(
        _SEPARABLE_Y_TRUE,
        _SEPARABLE_Y_PROB,
        "target_sensitivity",
        split_name="val",
        target_sensitivity=0.8,
    )
    assert result.target_achieved is True
    assert result.validation_metrics["sensitivity"] >= 0.8


def test_target_sensitivity_reports_failure_when_unreachable() -> None:
    # Predicting everyone positive always achieves sensitivity 1.0, so any target <= 1.0 is
    # technically reachable - exercise the "impossible target" branch directly via the
    # private helper instead of trying to construct data where the public API hits it.
    from medrisk_ml.evaluation.thresholding import _target_sensitivity

    threshold, achieved = _target_sensitivity(_SEPARABLE_Y_TRUE, _SEPARABLE_Y_PROB, target=1.5)
    assert achieved is False
    assert 0.0 <= threshold <= 1.0


def test_target_sensitivity_requires_target_value() -> None:
    with pytest.raises(ValueError, match="target_sensitivity"):
        select_threshold(
            _SEPARABLE_Y_TRUE, _SEPARABLE_Y_PROB, "target_sensitivity", split_name="val"
        )


def test_threshold_selection_on_test_split_raises() -> None:
    with pytest.raises(SplitLeakageError):
        select_threshold(_SEPARABLE_Y_TRUE, _SEPARABLE_Y_PROB, "fixed", split_name="test")


def test_unknown_strategy_raises() -> None:
    with pytest.raises(ValueError):
        select_threshold(
            _SEPARABLE_Y_TRUE, _SEPARABLE_Y_PROB, "not_a_real_strategy", split_name="val"
        )  # type: ignore[arg-type]


def test_single_class_input_does_not_crash() -> None:
    y_true = np.array([1, 1, 1, 1])
    y_prob = np.array([0.1, 0.9, 0.4, 0.6])
    result = select_threshold(y_true, y_prob, "max_f1", split_name="val")
    assert result.threshold == 0.5

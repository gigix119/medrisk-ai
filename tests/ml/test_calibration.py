from __future__ import annotations

import numpy as np
import pytest

from medrisk_ml.evaluation.calibration import (
    CalibrationFittingError,
    apply_calibration,
    expected_calibration_error,
    fit_temperature,
)

_RNG = np.random.default_rng(0)
_LABELS = np.array([0] * 20 + [1] * 20)
_LOGITS = np.concatenate([_RNG.normal(-2.0, 1.0, 20), _RNG.normal(2.0, 1.0, 20)])


def test_temperature_is_positive() -> None:
    result = fit_temperature(_LOGITS, _LABELS)
    assert result.temperature > 0


def test_calibrated_probabilities_are_valid() -> None:
    result = fit_temperature(_LOGITS, _LABELS)
    probabilities = apply_calibration(_LOGITS, result.temperature)
    assert np.all(probabilities >= 0.0)
    assert np.all(probabilities <= 1.0)
    assert np.all(np.isfinite(probabilities))


def test_fitting_rejects_empty_input() -> None:
    with pytest.raises(CalibrationFittingError):
        fit_temperature(np.array([]), np.array([]))


def test_fitting_rejects_single_class_labels() -> None:
    with pytest.raises(CalibrationFittingError):
        fit_temperature(np.array([0.1, 0.2, 0.3]), np.array([1, 1, 1]))


def test_apply_calibration_rejects_non_positive_temperature() -> None:
    with pytest.raises(ValueError, match="positive"):
        apply_calibration(_LOGITS, 0.0)
    with pytest.raises(ValueError, match="positive"):
        apply_calibration(_LOGITS, -1.0)


def test_expected_calibration_error_is_zero_for_perfectly_calibrated_groups() -> None:
    # Two bins, each with confidence exactly matching the observed frequency.
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    y_prob = np.array([0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0])
    assert expected_calibration_error(y_true, y_prob, n_bins=10) == 0.0


def test_expected_calibration_error_empty_input() -> None:
    assert np.isnan(expected_calibration_error(np.array([]), np.array([])))

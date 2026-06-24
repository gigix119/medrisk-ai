from __future__ import annotations

import math

import numpy as np

from medrisk_ml.evaluation.metrics import compute_binary_metrics, confusion_counts, sigmoid


def test_known_confusion_matrix_produces_expected_counts() -> None:
    y_true = np.array([1, 1, 0, 0, 1, 0])
    y_pred = np.array([1, 0, 0, 1, 1, 0])
    counts = confusion_counts(y_true, y_pred)
    assert counts.true_positive == 2
    assert counts.true_negative == 2
    assert counts.false_positive == 1
    assert counts.false_negative == 1
    assert counts.sample_count == 6
    assert counts.positive_count == 3
    assert counts.negative_count == 3


def test_sensitivity_and_specificity_are_correct() -> None:
    y_true = np.array([1, 1, 0, 0, 1, 0])
    y_prob = np.array([0.9, 0.2, 0.1, 0.8, 0.95, 0.3])
    metrics = compute_binary_metrics(y_true, y_prob, threshold=0.5)
    # predicted: [1, 0, 0, 1, 1, 0] vs true [1,1,0,0,1,0] -> tp=2,fn=1,tn=2,fp=1
    assert metrics["sensitivity"] == 2 / 3
    assert metrics["specificity"] == 2 / 3
    assert metrics["accuracy"] == 4 / 6


def test_accuracy_and_f1_known_values() -> None:
    y_true = np.array([1, 1, 1, 1, 0, 0, 0, 0])
    y_prob = np.array([0.9, 0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.1])
    metrics = compute_binary_metrics(y_true, y_prob, threshold=0.5)
    assert metrics["accuracy"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0


def test_roc_auc_undefined_with_single_class() -> None:
    y_true = np.array([1, 1, 1, 1])
    y_prob = np.array([0.1, 0.9, 0.4, 0.6])
    metrics = compute_binary_metrics(y_true, y_prob, threshold=0.5)
    assert math.isnan(metrics["roc_auc"])  # type: ignore[arg-type]
    assert math.isnan(metrics["pr_auc"])  # type: ignore[arg-type]
    # accuracy must still be computable even though ranking metrics are undefined.
    assert not math.isnan(metrics["accuracy"])  # type: ignore[arg-type]


def test_precision_undefined_when_no_positive_predictions() -> None:
    y_true = np.array([1, 0, 1, 0])
    y_prob = np.array([0.1, 0.1, 0.2, 0.05])
    metrics = compute_binary_metrics(y_true, y_prob, threshold=0.9)
    assert math.isnan(metrics["precision"])  # type: ignore[arg-type]


def test_empty_input_does_not_crash() -> None:
    metrics = compute_binary_metrics(np.array([]), np.array([]), threshold=0.5)
    assert metrics["sample_count"] == 0
    assert math.isnan(metrics["roc_auc"])  # type: ignore[arg-type]


def test_brier_score_perfect_predictions_is_zero() -> None:
    y_true = np.array([1.0, 0.0, 1.0, 0.0])
    y_prob = np.array([1.0, 0.0, 1.0, 0.0])
    metrics = compute_binary_metrics(y_true, y_prob, threshold=0.5)
    assert metrics["brier_score"] == 0.0


def test_brier_score_maximally_wrong_is_one() -> None:
    y_true = np.array([1.0, 0.0])
    y_prob = np.array([0.0, 1.0])
    metrics = compute_binary_metrics(y_true, y_prob, threshold=0.5)
    assert metrics["brier_score"] == 1.0


def test_sigmoid_matches_closed_form_for_moderate_values() -> None:
    logits = np.array([-2.0, 0.0, 2.0])
    expected = 1.0 / (1.0 + np.exp(-logits))
    np.testing.assert_allclose(sigmoid(logits), expected, atol=1e-6)


def test_sigmoid_does_not_overflow_on_extreme_values() -> None:
    logits = np.array([-1000.0, 1000.0])
    probs = sigmoid(logits)
    assert np.all(np.isfinite(probs))
    assert probs[0] < 1e-6
    assert probs[1] > 1 - 1e-6

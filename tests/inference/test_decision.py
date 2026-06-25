"""Unit tests for medrisk_inference.decision: calibration + the decision policy."""

from __future__ import annotations

import math

import pytest

from medrisk_inference.decision import apply_calibration, decide, parse_review_policy, sigmoid
from medrisk_inference.exceptions import CalibrationError, DecisionPolicyInvalidError
from medrisk_inference.types import ReviewPolicy


def test_sigmoid_matches_reference_values() -> None:
    assert sigmoid(0.0) == pytest.approx(0.5)
    assert sigmoid(100.0) == pytest.approx(1.0)
    assert sigmoid(-100.0) == pytest.approx(0.0)


def test_apply_calibration_without_temperature_is_plain_sigmoid() -> None:
    assert apply_calibration(0.0, None) == pytest.approx(0.5)
    assert apply_calibration(0.0, {}) == pytest.approx(0.5)


def test_apply_calibration_with_temperature_scales_logit() -> None:
    raw = apply_calibration(2.0, None)
    calibrated = apply_calibration(2.0, {"temperature": 2.0})
    assert calibrated == pytest.approx(sigmoid(1.0))
    assert calibrated != raw


def test_apply_calibration_rejects_non_finite_logit() -> None:
    with pytest.raises(CalibrationError):
        apply_calibration(math.inf, None)


def test_apply_calibration_rejects_invalid_temperature() -> None:
    with pytest.raises(CalibrationError):
        apply_calibration(1.0, {"temperature": 0})
    with pytest.raises(CalibrationError):
        apply_calibration(1.0, {"temperature": -5})


def test_parse_review_policy_none_is_none() -> None:
    assert parse_review_policy(None) is None


def test_parse_review_policy_valid() -> None:
    policy = parse_review_policy({"negative_probability_max": 0.4, "positive_probability_min": 0.6})
    assert policy == ReviewPolicy(negative_probability_max=0.4, positive_probability_min=0.6)


def test_parse_review_policy_rejects_missing_keys() -> None:
    with pytest.raises(DecisionPolicyInvalidError):
        parse_review_policy({"negative_probability_max": 0.4})


def test_parse_review_policy_rejects_inverted_bounds() -> None:
    with pytest.raises(DecisionPolicyInvalidError):
        parse_review_policy({"negative_probability_max": 0.6, "positive_probability_min": 0.4})


def test_parse_review_policy_rejects_out_of_range_bounds() -> None:
    with pytest.raises(DecisionPolicyInvalidError):
        parse_review_policy({"negative_probability_max": -0.1, "positive_probability_min": 0.6})


def test_decide_negative_boundary_without_review_policy() -> None:
    result = decide(
        0.2, threshold=0.5, positive_class="positive", negative_class="negative", review_policy=None
    )
    assert result.decision == "negative"
    assert result.predicted_class == "negative"
    assert result.predicted_class_probability == pytest.approx(0.8)
    assert result.confidence_score == pytest.approx(0.8)


def test_decide_positive_boundary_without_review_policy() -> None:
    result = decide(
        0.8, threshold=0.5, positive_class="positive", negative_class="negative", review_policy=None
    )
    assert result.decision == "positive"
    assert result.predicted_class == "positive"
    assert result.predicted_class_probability == pytest.approx(0.8)


def test_decide_exact_threshold_is_positive() -> None:
    result = decide(
        0.5, threshold=0.5, positive_class="positive", negative_class="negative", review_policy=None
    )
    assert result.predicted_class == "positive"
    assert result.decision == "positive"


def test_decide_review_required_middle_band() -> None:
    policy = ReviewPolicy(negative_probability_max=0.4, positive_probability_min=0.6)
    result = decide(
        0.5,
        threshold=0.5,
        positive_class="positive",
        negative_class="negative",
        review_policy=policy,
    )
    assert result.decision == "review_required"
    # predicted_class still reflects the plain threshold split, independent of the band.
    assert result.predicted_class == "positive"


def test_decide_review_policy_negative_boundary_is_inclusive() -> None:
    policy = ReviewPolicy(negative_probability_max=0.4, positive_probability_min=0.6)
    result = decide(
        0.4,
        threshold=0.5,
        positive_class="positive",
        negative_class="negative",
        review_policy=policy,
    )
    assert result.decision == "negative"


def test_decide_review_policy_positive_boundary_is_inclusive() -> None:
    policy = ReviewPolicy(negative_probability_max=0.4, positive_probability_min=0.6)
    result = decide(
        0.6,
        threshold=0.5,
        positive_class="positive",
        negative_class="negative",
        review_policy=policy,
    )
    assert result.decision == "positive"


def test_decide_rejects_invalid_threshold() -> None:
    with pytest.raises(DecisionPolicyInvalidError):
        decide(
            0.5,
            threshold=1.5,
            positive_class="positive",
            negative_class="negative",
            review_policy=None,
        )


def test_decide_uses_calibrated_not_raw_probability_semantics() -> None:
    """`decide` only ever sees one probability argument - calling code is responsible for
    passing the *calibrated* one. This test documents that contract at the boundary."""
    calibrated = apply_calibration(0.0, {"temperature": 4.0})
    result = decide(
        calibrated,
        threshold=0.5,
        positive_class="positive",
        negative_class="negative",
        review_policy=None,
    )
    assert result.calibrated_probability == pytest.approx(calibrated)

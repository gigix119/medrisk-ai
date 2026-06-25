"""Calibration application + the decision (negative / positive / review_required) policy.

Calibration parameters and the threshold/review policy are never re-fit here - they are
read verbatim from the verified bundle (see bundle.py) and applied as pure functions of a
single logit. This module has no PyTorch dependency at all: it only does float arithmetic,
which keeps it trivially unit-testable and import-light.
"""

from __future__ import annotations

import math
from typing import Any

from medrisk_inference.exceptions import CalibrationError, DecisionPolicyInvalidError
from medrisk_inference.types import DecisionResult, ReviewPolicy


def sigmoid(x: float) -> float:
    # Numerically stable for very negative x (avoids overflow in math.exp for large -x).
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


def apply_calibration(logit: float, calibration: dict[str, Any] | None) -> float:
    """Map a raw logit to a calibrated probability in [0, 1].

    With no calibration metadata (or an empty dict), this is a plain sigmoid. With a stored
    `temperature`, it is temperature-scaled sigmoid: `sigmoid(logit / temperature)`.
    """
    if not math.isfinite(logit):
        raise CalibrationError(f"Logit is not finite: {logit!r}")

    temperature = (calibration or {}).get("temperature")
    if temperature is None:
        probability = sigmoid(logit)
    else:
        if not isinstance(temperature, int | float) or temperature <= 0:
            raise CalibrationError(f"Invalid calibration temperature: {temperature!r}")
        probability = sigmoid(logit / temperature)

    if not math.isfinite(probability) or not (0.0 <= probability <= 1.0):
        raise CalibrationError(f"Calibrated probability out of range: {probability!r}")
    return probability


def parse_review_policy(review_policy: dict[str, Any] | None) -> ReviewPolicy | None:
    """Parse+validate the bundle's review policy. `None` means "no review band": the
    decision pipeline falls back to a plain two-way (negative/positive) split on `threshold`.
    """
    if review_policy is None:
        return None
    try:
        negative_max = float(review_policy["negative_probability_max"])
        positive_min = float(review_policy["positive_probability_min"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DecisionPolicyInvalidError(
            f"review_policy must contain numeric 'negative_probability_max' and "
            f"'positive_probability_min', got: {review_policy!r}"
        ) from exc

    if not (0.0 <= negative_max < positive_min <= 1.0):
        raise DecisionPolicyInvalidError(
            "review_policy bounds must satisfy "
            f"0 <= negative_probability_max ({negative_max}) < "
            f"positive_probability_min ({positive_min}) <= 1"
        )
    return ReviewPolicy(
        negative_probability_max=negative_max, positive_probability_min=positive_min
    )


def decide(
    calibrated_probability: float,
    *,
    threshold: float,
    positive_class: str,
    negative_class: str,
    review_policy: ReviewPolicy | None,
) -> DecisionResult:
    """Combine the threshold-based predicted class with the (optional) review-required band.

    `predicted_class` always reflects a plain threshold split - it is informative even when
    `decision` is `review_required`. `decision` is the policy-aware, user-facing verdict:
    with a review policy it is three-way (negative/positive/review_required); without one,
    it collapses to mirror `predicted_class`. The bundle's threshold is never silently
    replaced with 0.5.
    """
    if not (0.0 <= threshold <= 1.0):
        raise DecisionPolicyInvalidError(f"threshold must be in [0, 1], got: {threshold!r}")

    is_positive = calibrated_probability >= threshold
    predicted_class = positive_class if is_positive else negative_class
    predicted_class_probability = (
        calibrated_probability if is_positive else 1.0 - calibrated_probability
    )
    confidence_score = max(calibrated_probability, 1.0 - calibrated_probability)

    decision: str
    if review_policy is not None:
        if calibrated_probability <= review_policy.negative_probability_max:
            decision = "negative"
        elif calibrated_probability >= review_policy.positive_probability_min:
            decision = "positive"
        else:
            decision = "review_required"
    else:
        decision = "positive" if is_positive else "negative"

    return DecisionResult(
        calibrated_probability=calibrated_probability,
        predicted_class=predicted_class,
        predicted_class_probability=predicted_class_probability,
        confidence_score=confidence_score,
        decision=decision,  # type: ignore[arg-type]
        threshold=threshold,
        review_policy=review_policy,
    )

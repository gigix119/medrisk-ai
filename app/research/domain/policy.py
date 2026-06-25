"""Scientific-integrity policy: disclaimer text and small structural guards.

Centralizes the wording the research platform must show on every research-facing view, plus
a couple of validation helpers that make specific bad practices structurally impossible
rather than merely documented as "don't do this" - mirroring how
`medrisk_ml.evaluation.thresholding.select_threshold` already raises `SplitLeakageError`
when asked to select a threshold against the test split.
"""

from __future__ import annotations

from app.research.domain.enums import ScientificMaturity

RESEARCH_DISCLAIMER_EN = (
    "Research and educational use only. Not a medical device. Not clinically validated. "
    "Model outputs must not be used for diagnosis or treatment decisions."
)

RESEARCH_DISCLAIMER_PL = (
    "Wyłącznie do celów badawczych i edukacyjnych. Nie jest wyrobem medycznym. Nie zostało "
    "klinicznie zweryfikowane. Wyniki modelu nie mogą być używane do diagnozy ani podejmowania "
    "decyzji terapeutycznych."
)

SYNTHETIC_RESULT_NOTICE_EN = (
    "Demonstration-only result based on synthetic or fixture data. It does not represent real "
    "medical performance."
)

SYNTHETIC_RESULT_NOTICE_PL = (
    "Wynik wyłącznie demonstracyjny, oparty na danych syntetycznych lub testowych. Nie "
    "odzwierciedla rzeczywistej skuteczności medycznej."
)

# Labels that must never appear anywhere in generated research-facing text (model cards,
# dataset cards, reports, UI strings) - checked by `assert_not_forbidden_label`, not just
# avoided by convention.
_FORBIDDEN_MATURITY_LABELS = {
    "clinically validated",
    "medically approved",
    "safe for diagnosis",
    "production medical model",
    "doctor-level accuracy",
}


class SplitProtocolViolationError(ValueError):
    """Raised when a study configuration or service call would fit calibration parameters,
    tune a decision threshold, or otherwise adapt to the held-out test split."""


def reject_test_split_fitting(*, purpose: str, split_name: str) -> None:
    """Call before fitting/selecting anything that must never see the test split. This is the
    research-platform-level counterpart to `medrisk_ml.evaluation.thresholding`'s
    `SplitLeakageError` - it guards study-config validation and evaluation-run creation, not
    just the training pipeline itself."""
    if split_name == "test":
        raise SplitProtocolViolationError(
            f"{purpose} must never be fit or tuned against the 'test' split - use 'val' instead."
        )


def is_demonstration_only(maturity: ScientificMaturity) -> bool:
    return maturity == ScientificMaturity.SYNTHETIC_DEMO


def assert_not_forbidden_label(label: str) -> None:
    """Defense in depth against accidentally writing one of the explicitly banned marketing
    labels into generated text - raises rather than silently rendering it."""
    if label.strip().lower() in _FORBIDDEN_MATURITY_LABELS:
        raise ValueError(
            f"{label!r} is a forbidden scientific-maturity label and must never be used."
        )

"""Constants shared across the inference package."""

from __future__ import annotations

from typing import Final

MEDICAL_DISCLAIMER: Final[str] = (
    "This software is an educational and research portfolio project. "
    "It is not a medical device and must not be used for diagnosis, "
    "treatment decisions, or emergency medical guidance."
)

SYNTHETIC_MODEL_WARNING: Final[str] = "Synthetic test model. This result has no medical meaning."

GRADCAM_DISCLAIMER: Final[str] = (
    "Grad-CAM highlights regions associated with the model output. "
    "It is not a biological explanation and must not be used as a diagnosis."
)

SUPPORTED_IMAGE_FORMATS: Final[tuple[str, ...]] = ("PNG", "JPEG")

BUNDLE_FILES: Final[tuple[str, ...]] = (
    "model_state.pt",
    "manifest.json",
    "preprocessing.json",
    "threshold.json",
    "calibration.json",
    "model_card.md",
    "SHA256SUMS",
)

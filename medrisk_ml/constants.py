"""Project-wide constants: paths, class semantics, normalization stats, disclaimers."""

from __future__ import annotations

from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

# --- Dataset / class semantics -------------------------------------------------
PCAM_IMAGE_SIZE: Final[int] = 96
PCAM_CHANNELS: Final[int] = 3
CLASS_NAMES: Final[tuple[str, str]] = ("negative", "positive")
POSITIVE_CLASS_INDEX: Final[int] = 1

# ImageNet normalization stats, required for torchvision pretrained ResNet18 weights.
IMAGENET_MEAN: Final[tuple[float, float, float]] = (0.485, 0.456, 0.406)
IMAGENET_STD: Final[tuple[float, float, float]] = (0.229, 0.224, 0.225)

# --- Environment / safety gates ------------------------------------------------
ALLOW_DATA_DOWNLOAD_ENV_VAR: Final[str] = "MEDRISK_ALLOW_DATA_DOWNLOAD"

# --- Artifact layout ------------------------------------------------------------
ARTIFACTS_DIR_NAME: Final[str] = "artifacts"
EXPERIMENTS_DIR_NAME: Final[str] = "experiments"
MODEL_REGISTRY_DIR_NAME: Final[str] = "model_registry"
EXPERIMENT_REGISTRY_RELATIVE_PATH: Final[str] = "artifacts/registry/experiments.jsonl"

# --- Disclaimers (must appear in every report/model card touching predictions) -
MEDICAL_DISCLAIMER: Final[str] = (
    "This software is an educational and research portfolio project.\n"
    "It is not a medical device and must not be used for diagnosis,\n"
    "treatment decisions, or emergency medical guidance."
)

GRADCAM_DISCLAIMER: Final[str] = (
    "Grad-CAM highlights regions associated with the model output.\n"
    "It is not a biological explanation and must not be used as a diagnosis."
)

SYNTHETIC_DATA_WARNING: Final[str] = "SYNTHETIC DATA — NOT MEDICAL PERFORMANCE"
SYNTHETIC_SMOKE_EXPERIMENT_WARNING: Final[str] = (
    "SYNTHETIC SMOKE EXPERIMENT\nNOT A MEDICAL PERFORMANCE RESULT"
)

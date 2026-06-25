"""Inference runtime configuration.

A plain dataclass, not a pydantic-settings class: medrisk_inference must stay importable
(and testable, and usable from the CLI) without FastAPI or the app's Settings class. The
app translates its own Settings into this dataclass once, in app/services/model_deployment.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DeviceRequest = Literal["auto", "cpu", "cuda", "mps"]
EnvironmentName = Literal["development", "test", "production"]


@dataclass(frozen=True)
class InferenceConfig:
    environment: EnvironmentName = "development"

    model_bundle_path: str | None = None
    model_device: DeviceRequest = "auto"
    model_warmup_enabled: bool = True
    model_strict_version_check: bool = True
    allow_synthetic_model: bool = False

    inference_timeout_seconds: float = 20.0
    inference_queue_timeout_seconds: float = 5.0
    inference_max_concurrency: int = 1

    max_upload_bytes: int = 5_242_880
    max_image_width: int = 4096
    max_image_height: int = 4096
    max_image_pixels: int = 16_777_216
    min_image_width: int = 32
    min_image_height: int = 32
    strict_model_input_shape: bool = True

    gradcam_enabled: bool = True
    gradcam_max_output_bytes: int = 500_000

    @property
    def synthetic_model_allowed(self) -> bool:
        """Synthetic bundles are allowed in `test`, or in `development` with the explicit
        opt-in flag set. Never in `production` (also hard-enforced by app Settings)."""
        if self.environment == "test":
            return True
        return self.environment == "development" and self.allow_synthetic_model

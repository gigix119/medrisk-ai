"""Grad-CAM explanation generation: reuses medrisk_ml's GradCAM/hook implementation, but
renders the overlay with plain Pillow/NumPy (no matplotlib) so the inference image stays
free of training-only/plotting dependencies - see docs/inference-architecture.md.
"""

from __future__ import annotations

import base64
import time
from io import BytesIO

import numpy as np
import torch
from PIL import Image

from medrisk_inference.constants import GRADCAM_DISCLAIMER
from medrisk_inference.exceptions import ExplanationFailedError, ExplanationNotSupportedError
from medrisk_inference.types import ExplanationResult
from medrisk_ml.explainability.gradcam import GradCAM
from medrisk_ml.models.factory import UnknownArchitectureError, get_target_layer

_OVERLAY_ALPHA = 0.45
_OVERLAY_COLOR = np.array([255.0, 0.0, 0.0])  # red highlight, no matplotlib colormap needed

_TARGET_LAYER_NAMES = {"resnet18": "layer4", "baseline_cnn": "features.-1 (last conv block)"}


def generate_explanation(
    model: torch.nn.Module,
    architecture: str,
    input_tensor: torch.Tensor,
    base_rgb_image: Image.Image,
    *,
    max_output_bytes: int,
) -> ExplanationResult:
    """`base_rgb_image` must already be at the processed (model input) resolution."""
    started = time.perf_counter()
    try:
        target_layer = get_target_layer(model, architecture)  # type: ignore[arg-type]
    except UnknownArchitectureError as exc:
        raise ExplanationNotSupportedError(str(exc)) from exc

    try:
        with GradCAM(model, target_layer) as cam:
            heatmap = cam.generate(input_tensor)

        overlay = _overlay_heatmap(base_rgb_image, heatmap)
        buffer = BytesIO()
        overlay.save(buffer, format="PNG", optimize=True)
        encoded = buffer.getvalue()
        if len(encoded) > max_output_bytes:
            raise ExplanationFailedError(
                f"Encoded explanation ({len(encoded)} bytes) exceeds the "
                f"{max_output_bytes}-byte limit."
            )
    except ExplanationFailedError:
        raise
    except Exception as exc:  # defensive: explanation failures must never crash a prediction
        raise ExplanationFailedError(f"Grad-CAM generation failed: {exc}") from exc

    generation_time_ms = (time.perf_counter() - started) * 1000
    return ExplanationResult(
        status="available",
        method="grad_cam",
        target_layer=_TARGET_LAYER_NAMES.get(architecture, architecture),
        mime_type="image/png",
        encoding="base64",
        data=base64.b64encode(encoded).decode("ascii"),
        width=overlay.width,
        height=overlay.height,
        generation_time_ms=generation_time_ms,
        disclaimer=GRADCAM_DISCLAIMER,
    )


def _overlay_heatmap(base_rgb_image: Image.Image, heatmap: np.ndarray) -> Image.Image:
    base_array = np.asarray(base_rgb_image, dtype=np.float64)
    weight = (_OVERLAY_ALPHA * heatmap)[..., None]
    blended = base_array * (1.0 - weight) + _OVERLAY_COLOR * weight
    blended = np.clip(blended, 0, 255).astype(np.uint8)
    return Image.fromarray(blended, mode="RGB")

"""Heatmap <-> image compositing for Grad-CAM outputs (matplotlib colormap, no OpenCV)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from matplotlib import colormaps
from PIL import Image


def overlay_heatmap(
    image: np.ndarray, heatmap: np.ndarray, alpha: float = 0.4, colormap: str = "jet"
) -> np.ndarray:
    """`image` is HxWx3 uint8; `heatmap` is HxW float in [0, 1], already resized to match.

    Returns an HxWx3 uint8 alpha-blended composite.
    """
    if image.shape[:2] != heatmap.shape:
        raise ValueError(
            f"image spatial shape {image.shape[:2]} does not match heatmap shape {heatmap.shape}"
        )
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be in [0, 1]")
    cmap = colormaps[colormap]
    colored = cmap(heatmap)[:, :, :3]  # drop the colormap's alpha channel
    colored_uint8 = (colored * 255).astype(np.float64)
    blended = image.astype(np.float64) * (1 - alpha) + colored_uint8 * alpha
    result: np.ndarray = np.clip(blended, 0, 255).astype(np.uint8)
    return result


def save_overlay(
    image: np.ndarray,
    heatmap: np.ndarray,
    output_path: Path,
    alpha: float = 0.4,
    colormap: str = "jet",
) -> Path:
    composite = overlay_heatmap(image, heatmap, alpha=alpha, colormap=colormap)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(composite, mode="RGB").save(output_path)
    return output_path

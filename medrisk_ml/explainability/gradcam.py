"""Grad-CAM (Selvaraju et al., 2017): class activation mapping via gradients.

Implemented directly against `target_layer`, no third-party Grad-CAM library - small
enough to own, audit, and unit-test. Binary single-logit models have no class index to
choose between; Grad-CAM always backpropagates from that one logit (optionally negated via
`target_sign=-1.0` to see what pushed the prediction toward "negative" instead).

GRAD-CAM DISCLAIMER: highlights regions associated with the model output. It is not a
biological explanation and must not be used as a diagnosis (see docs/explainability.md).
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

from medrisk_ml.explainability.hooks import ActivationsAndGradients


class GradCAM:
    def __init__(self, model: nn.Module, target_layer: nn.Module) -> None:
        self.model = model
        self._hooks = ActivationsAndGradients(model, target_layer)

    def __enter__(self) -> GradCAM:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()

    def release(self) -> None:
        self._hooks.release()

    def generate(self, input_tensor: torch.Tensor, target_sign: float = 1.0) -> np.ndarray:
        """`input_tensor` is a single-image batch of shape (1, C, H, W).

        Returns an (H, W) heatmap normalized to [0, 1] - an all-zero array (not a
        div-by-zero crash) when activations/gradients are degenerate, e.g. a perfectly
        flat heatmap or non-finite values.
        """
        if input_tensor.dim() != 4 or input_tensor.shape[0] != 1:
            raise ValueError(
                f"Expected a single-image batch (1, C, H, W), got shape {tuple(input_tensor.shape)}"
            )

        was_training = self.model.training
        self.model.eval()
        try:
            with torch.enable_grad():
                input_tensor = input_tensor.clone().requires_grad_(True)
                logit = self._hooks(input_tensor).reshape(-1)[0]
                self.model.zero_grad(set_to_none=True)
                (target_sign * logit).backward()

                activations = self._hooks.activations
                gradients = self._hooks.gradients
                if activations is None or gradients is None:
                    raise RuntimeError(
                        "Grad-CAM hooks did not fire - is target_layer part of the model graph?"
                    )

                weights = gradients.mean(dim=(2, 3), keepdim=True)
                weighted_combination = (weights * activations).sum(dim=1, keepdim=True)
                heatmap = F.relu(weighted_combination)
                heatmap = F.interpolate(
                    heatmap, size=input_tensor.shape[2:], mode="bilinear", align_corners=False
                )
                heatmap_np = heatmap.detach().cpu().numpy()[0, 0]
        finally:
            if was_training:
                self.model.train()

        return _normalize(heatmap_np)


def _normalize(heatmap: np.ndarray) -> np.ndarray:
    if not np.all(np.isfinite(heatmap)):
        return np.zeros_like(heatmap)
    minimum = float(heatmap.min())
    maximum = float(heatmap.max())
    if maximum - minimum < 1e-12:
        return np.zeros_like(heatmap)
    return (heatmap - minimum) / (maximum - minimum)

"""Forward/backward hook management for Grad-CAM.

Captures the target layer's forward activations and the gradient flowing into them, via a
forward hook that also registers a tensor-level gradient hook on its own output - more
robust across architectures than a module-level `register_full_backward_hook`, which has
historically had edge cases with in-place ops and non-leaf module boundaries.
"""

from __future__ import annotations

import torch
from torch import nn
from torch.utils.hooks import RemovableHandle


class ActivationsAndGradients:
    def __init__(self, model: nn.Module, target_layer: nn.Module) -> None:
        self.model = model
        self.activations: torch.Tensor | None = None
        self.gradients: torch.Tensor | None = None
        self._handles: list[RemovableHandle] = [
            target_layer.register_forward_hook(self._save_activation)
        ]

    def _save_activation(
        self, module: nn.Module, inputs: tuple[torch.Tensor, ...], output: torch.Tensor
    ) -> None:
        self.activations = output
        output.register_hook(self._save_gradient)

    def _save_gradient(self, grad: torch.Tensor) -> None:
        self.gradients = grad

    def __call__(self, x: torch.Tensor) -> torch.Tensor:
        self.activations = None
        self.gradients = None
        result: torch.Tensor = self.model(x)
        return result

    def release(self) -> None:
        for handle in self._handles:
            handle.remove()
        self._handles = []

    def __enter__(self) -> ActivationsAndGradients:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()

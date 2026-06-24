"""Optimizer construction. Only parameters with `requires_grad=True` are passed in, so a
frozen ResNet18 backbone is never given to the optimizer in the first place.
"""

from __future__ import annotations

import torch
from torch import nn

from medrisk_ml.types import OptimizerName


def build_optimizer(
    model: nn.Module,
    name: OptimizerName,
    learning_rate: float,
    weight_decay: float = 0.0,
) -> torch.optim.Optimizer:
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    if not trainable_params:
        raise ValueError("Model has no trainable parameters (everything is frozen)")
    if name == "adamw":
        return torch.optim.AdamW(trainable_params, lr=learning_rate, weight_decay=weight_decay)
    if name == "sgd":
        return torch.optim.SGD(
            trainable_params, lr=learning_rate, weight_decay=weight_decay, momentum=0.9
        )
    raise ValueError(f"Unknown optimizer: {name!r}")

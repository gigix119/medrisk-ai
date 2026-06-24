"""Loss construction. BCEWithLogitsLoss is the only supported loss for this binary task -
it fuses sigmoid + binary cross-entropy into one numerically stable operation.
"""

from __future__ import annotations

import torch
from torch import nn


def build_loss(pos_weight: float | None = None) -> nn.Module:
    """`nn.BCEWithLogitsLoss`, optionally with a positive-class weight for imbalance."""
    weight_tensor = torch.tensor(pos_weight) if pos_weight is not None else None
    return nn.BCEWithLogitsLoss(pos_weight=weight_tensor)

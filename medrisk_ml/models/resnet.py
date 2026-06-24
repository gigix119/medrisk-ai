"""ResNet18 transfer learning via torchvision, with staged freeze/unfreeze support.

Stage A (default): freeze the pretrained backbone, train only the replaced classifier
head. Stage B (optional fine-tuning): unfreeze from a chosen layer onward with a lower
learning rate, configured via `--set model.freeze_backbone=false --set
model.unfreeze_from_layer=layer4` (see docs/experiment-protocol.md).
"""

from __future__ import annotations

from torch import nn
from torchvision.models import ResNet18_Weights, resnet18

_UNFREEZE_ORDER = ("conv1", "bn1", "layer1", "layer2", "layer3", "layer4", "fc")


def build_resnet18(
    pretrained: bool = True,
    dropout: float = 0.2,
    freeze_backbone: bool = True,
    unfreeze_from_layer: str | None = None,
) -> nn.Module:
    """Build a ResNet18 with its head replaced by a single-logit classifier.

    Returns raw logits of shape (batch, 1), matching `BaselineCNN`'s contract - see that
    module's docstring for why logits (not probabilities) are returned.
    """
    weights = ResNet18_Weights.DEFAULT if pretrained else None
    model = resnet18(weights=weights)
    in_features = model.fc.in_features
    model.fc = nn.Sequential(nn.Dropout(dropout), nn.Linear(in_features, 1))

    if freeze_backbone:
        for name, param in model.named_parameters():
            param.requires_grad = name.startswith("fc.")

    if unfreeze_from_layer is not None:
        if unfreeze_from_layer not in _UNFREEZE_ORDER:
            raise ValueError(
                f"Unknown layer name for unfreeze_from_layer: {unfreeze_from_layer!r}; "
                f"expected one of {_UNFREEZE_ORDER}"
            )
        start = _UNFREEZE_ORDER.index(unfreeze_from_layer)
        for layer_name in _UNFREEZE_ORDER[start:]:
            layer = getattr(model, layer_name)
            for param in layer.parameters():
                param.requires_grad = True

    result: nn.Module = model
    return result

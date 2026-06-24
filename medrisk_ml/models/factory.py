"""Validated architecture construction + parameter/target-layer metadata.

The factory never touches HTTP or backend code - it is a pure `str -> (nn.Module,
ModelMetadata)` mapping, independent of the YAML config layer (`medrisk_ml.config`), so
callers pass plain primitives rather than a config object.
"""

from __future__ import annotations

from dataclasses import dataclass

from torch import nn

from medrisk_ml.models.baseline_cnn import BaselineCNN, BaselineCNNConfig
from medrisk_ml.models.resnet import build_resnet18
from medrisk_ml.types import ArchitectureName

_KNOWN_ARCHITECTURES: tuple[ArchitectureName, ...] = ("baseline_cnn", "resnet18")


class UnknownArchitectureError(ValueError):
    """Raised when an architecture name outside `_KNOWN_ARCHITECTURES` is requested."""


@dataclass(frozen=True)
class ModelMetadata:
    architecture: ArchitectureName
    total_parameters: int
    trainable_parameters: int
    input_shape: tuple[int, int, int]
    output_shape: tuple[int, ...]


def count_parameters(model: nn.Module) -> tuple[int, int]:
    """(total parameters, trainable parameters)."""
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return total, trainable


def get_target_layer(model: nn.Module, architecture: ArchitectureName) -> nn.Module:
    """The convolutional layer Grad-CAM should hook into for this architecture."""
    if architecture == "resnet18":
        target = model.layer4
    elif architecture == "baseline_cnn":
        target = model.features[-1]  # type: ignore[index]
    else:
        raise UnknownArchitectureError(architecture)
    assert isinstance(
        target, nn.Module
    ), f"Expected target layer to be an nn.Module, got {type(target)}"
    return target


def build_model(
    architecture: ArchitectureName,
    *,
    pretrained: bool = False,
    dropout: float = 0.3,
    freeze_backbone: bool = False,
    unfreeze_from_layer: str | None = None,
    input_channels: int = 3,
    image_size: int = 96,
) -> tuple[nn.Module, ModelMetadata]:
    """Build a validated model + its parameter/shape metadata.

    Raises `UnknownArchitectureError` for any name outside {"baseline_cnn", "resnet18"}.
    """
    if architecture not in _KNOWN_ARCHITECTURES:
        raise UnknownArchitectureError(
            f"Unknown architecture {architecture!r}; expected one of {_KNOWN_ARCHITECTURES}"
        )

    model: nn.Module
    if architecture == "baseline_cnn":
        model = BaselineCNN(BaselineCNNConfig(input_channels=input_channels, dropout=dropout))
    else:
        model = build_resnet18(
            pretrained=pretrained,
            dropout=dropout,
            freeze_backbone=freeze_backbone,
            unfreeze_from_layer=unfreeze_from_layer,
        )

    total, trainable = count_parameters(model)
    metadata = ModelMetadata(
        architecture=architecture,
        total_parameters=total,
        trainable_parameters=trainable,
        input_shape=(input_channels, image_size, image_size),
        output_shape=(1,),
    )
    return model, metadata

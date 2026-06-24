"""A small, from-scratch CNN baseline - simple enough to explain in a junior interview.

Four Conv-BatchNorm-ReLU-MaxPool blocks doubling channels (32 -> 64 -> 128 -> 256), global
average pooling, dropout, and a single linear layer to one logit.

The model returns raw logits of shape (batch, 1), never a sigmoided probability: training
uses `nn.BCEWithLogitsLoss`, which combines the sigmoid and the binary cross-entropy into
one numerically stable operation (avoiding the log(0) that a naive sigmoid-then-BCE can hit
when the sigmoid saturates). `torch.sigmoid(logits)` is only applied at evaluation/inference
time, when an actual probability is needed.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn


@dataclass(frozen=True)
class BaselineCNNConfig:
    input_channels: int = 3
    dropout: float = 0.3


def _conv_block(in_channels: int, out_channels: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
        nn.BatchNorm2d(out_channels),
        nn.ReLU(inplace=True),
        nn.MaxPool2d(kernel_size=2),
    )


class BaselineCNN(nn.Module):
    def __init__(self, config: BaselineCNNConfig | None = None) -> None:
        super().__init__()
        self.config = config or BaselineCNNConfig()
        channels = self.config.input_channels
        self.features = nn.Sequential(
            _conv_block(channels, 32),
            _conv_block(32, 64),
            _conv_block(64, 128),
            _conv_block(128, 256),
        )
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(self.config.dropout),
            nn.Linear(256, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Returns raw logits of shape (batch, 1)."""
        x = self.features(x)
        x = self.pool(x)
        logits: torch.Tensor = self.classifier(x)
        return logits

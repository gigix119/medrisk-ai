"""LR scheduler construction, normalized behind one `.step(metric=...)` interface.

`ReduceLROnPlateau.step()` takes a metric argument; `CosineAnnealingLR.step()` does not.
`SchedulerWrapper` hides that difference so the training loop calls `.step()` the same way
regardless of which scheduler (or none) is configured. The underlying scheduler types have
genuinely incompatible signatures (a PyTorch API inconsistency, not ours to fix), so the
wrapped attribute is typed `Any`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch

from medrisk_ml.types import MonitorMode, SchedulerName


@dataclass
class SchedulerWrapper:
    name: SchedulerName
    scheduler: Any

    def step(self, metric: float | None = None) -> None:
        if self.scheduler is None:
            return
        if self.name == "reduce_on_plateau":
            if metric is None:
                raise ValueError("reduce_on_plateau requires a metric value on step()")
            self.scheduler.step(metric)
        else:
            self.scheduler.step()

    def state_dict(self) -> dict[str, Any] | None:
        if self.scheduler is None:
            return None
        result: dict[str, Any] = self.scheduler.state_dict()
        return result


def build_scheduler(
    optimizer: torch.optim.Optimizer,
    name: SchedulerName,
    monitored_mode: MonitorMode = "max",
    epochs: int = 1,
) -> SchedulerWrapper:
    if name == "none":
        return SchedulerWrapper(name=name, scheduler=None)
    if name == "reduce_on_plateau":
        plateau_scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode=monitored_mode, patience=2, factor=0.5
        )
        return SchedulerWrapper(name=name, scheduler=plateau_scheduler)
    if name == "cosine":
        cosine_scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=max(epochs, 1)
        )
        return SchedulerWrapper(name=name, scheduler=cosine_scheduler)
    raise ValueError(f"Unknown scheduler: {name!r}")


def current_lr(optimizer: torch.optim.Optimizer) -> float:
    return float(optimizer.param_groups[0]["lr"])

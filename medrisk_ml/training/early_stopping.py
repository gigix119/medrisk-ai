"""Early stopping on a monitored validation metric.

Must never be wired to test metrics - the trainer only ever calls `step()` with a
validation-split value. See docs/experiment-protocol.md for why.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from medrisk_ml.types import MonitorMode


@dataclass
class EarlyStopping:
    patience: int
    mode: MonitorMode = "max"
    min_delta: float = 0.0
    best_value: float = field(default=0.0, init=False)
    best_epoch: int = field(default=0, init=False)
    counter: int = field(default=0, init=False)
    should_stop: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self.best_value = float("-inf") if self.mode == "max" else float("inf")

    def _is_improvement(self, value: float) -> bool:
        if self.mode == "max":
            return value > self.best_value + self.min_delta
        return value < self.best_value - self.min_delta

    def step(self, value: float, epoch: int) -> bool:
        """Update state for this epoch's monitored value. Returns True once should_stop."""
        if self._is_improvement(value):
            self.best_value = value
            self.best_epoch = epoch
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True
        return self.should_stop

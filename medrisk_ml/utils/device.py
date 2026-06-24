"""Device resolution for "auto"/"cuda"/"mps"/"cpu" requests.

Centralizing this means no other module ever calls `.cuda()` directly or guesses
whether a backend is usable - they all go through `resolve_device`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import torch

from medrisk_ml.utils.logging import get_logger

logger = get_logger(__name__)

DeviceRequest = Literal["auto", "cuda", "mps", "cpu"]


class DeviceUnavailableError(RuntimeError):
    """Raised when the caller explicitly requests a backend that isn't actually usable."""


@dataclass(frozen=True)
class ResolvedDevice:
    device: torch.device
    requested: str
    device_name: str
    device_count: int

    @property
    def supports_amp(self) -> bool:
        """CUDA automatic mixed precision is the only AMP path this project enables."""
        return self.device.type == "cuda"


def _mps_available() -> bool:
    backend = getattr(torch.backends, "mps", None)
    return bool(backend is not None and backend.is_available())


def resolve_device(requested: DeviceRequest = "auto") -> ResolvedDevice:
    """Resolve a device request to a concrete, verified-available `torch.device`.

    "auto" prefers CUDA, then MPS, then CPU. Explicitly requesting an unavailable
    backend raises `DeviceUnavailableError` rather than silently falling back.
    """
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise DeviceUnavailableError(
                "CUDA was explicitly requested but torch.cuda.is_available() is False."
            )
        return _build("cuda", requested)
    if requested == "mps":
        if not _mps_available():
            raise DeviceUnavailableError(
                "MPS was explicitly requested but torch.backends.mps.is_available() is False."
            )
        return _build("mps", requested)
    if requested == "cpu":
        return _build("cpu", requested)
    if requested == "auto":
        if torch.cuda.is_available():
            return _build("cuda", requested)
        if _mps_available():
            return _build("mps", requested)
        return _build("cpu", requested)
    raise ValueError(f"Unknown device request: {requested!r}")


def _build(kind: str, requested: str) -> ResolvedDevice:
    device = torch.device(kind)
    if kind == "cuda":
        name = torch.cuda.get_device_name(device)
        count = torch.cuda.device_count()
    elif kind == "mps":
        name = "Apple MPS"
        count = 1
    else:
        name = "CPU"
        count = 1
    resolved = ResolvedDevice(
        device=device, requested=requested, device_name=name, device_count=count
    )
    logger.info(
        "Resolved device request=%s -> type=%s name=%s count=%d",
        requested,
        kind,
        name,
        count,
    )
    return resolved

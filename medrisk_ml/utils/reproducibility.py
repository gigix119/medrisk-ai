"""Seeding and environment-metadata capture for reproducible experiments.

Bitwise reproducibility is NOT guaranteed across different GPUs, CUDA/cuDNN
versions, or driver versions - only across repeated runs on the same machine
with the same library versions and `deterministic=True`. This module records
enough metadata that a later run can at least confirm whether conditions match.
"""

from __future__ import annotations

import platform
import random
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch

_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ReproducibilityReport:
    seed: int
    deterministic_requested: bool
    deterministic_algorithms_enabled: bool
    cudnn_benchmark: bool
    warnings: tuple[str, ...] = field(default_factory=tuple)


def set_seed(seed: int, deterministic: bool = False) -> ReproducibilityReport:
    """Seed Python/NumPy/PyTorch (CPU + all CUDA devices) and configure determinism."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    collected_warnings: list[str] = []
    deterministic_enabled = False
    if deterministic:
        try:
            torch.use_deterministic_algorithms(True)
            deterministic_enabled = True
        except RuntimeError as exc:
            collected_warnings.append(
                f"torch.use_deterministic_algorithms(True) could not be fully enabled: {exc}"
            )
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        collected_warnings.append(
            "Deterministic mode trades performance for reproducibility; exact bitwise "
            "reproducibility across different GPUs/driver versions is still not guaranteed."
        )
    else:
        torch.backends.cudnn.benchmark = torch.cuda.is_available()

    return ReproducibilityReport(
        seed=seed,
        deterministic_requested=deterministic,
        deterministic_algorithms_enabled=deterministic_enabled,
        cudnn_benchmark=torch.backends.cudnn.benchmark,
        warnings=tuple(collected_warnings),
    )


def seed_worker(worker_id: int) -> None:
    """`DataLoader(worker_init_fn=...)` target so each worker gets a reproducible, distinct seed."""
    worker_seed = torch.initial_seed() % 2**32
    np.random.seed(worker_seed)
    random.seed(worker_seed)


def _git_command(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            cwd=_REPO_ROOT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def get_git_commit() -> str | None:
    """Current commit hash, or None when Git is unavailable (recorded honestly, never faked)."""
    return _git_command(["rev-parse", "HEAD"])


def is_git_dirty() -> bool | None:
    """Whether the working tree has uncommitted changes, or None when Git is unavailable."""
    status = _git_command(["status", "--porcelain"])
    if status is None:
        return None
    return len(status) > 0


def _torchvision_version() -> str | None:
    try:
        import torchvision
    except ImportError:
        return None
    version: str = torchvision.__version__
    return version


def collect_environment_metadata() -> dict[str, Any]:
    """Snapshot of interpreter/library/hardware facts to store alongside every experiment."""
    cuda_available = torch.cuda.is_available()
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "torchvision_version": _torchvision_version(),
        "cuda_available": cuda_available,
        "cuda_version": torch.version.cuda if cuda_available else None,
        "cudnn_version": torch.backends.cudnn.version() if cuda_available else None,
        "device_name": torch.cuda.get_device_name(0) if cuda_available else None,
        "git_commit": get_git_commit(),
        "git_dirty": is_git_dirty(),
    }

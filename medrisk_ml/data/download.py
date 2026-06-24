"""Gated, safety-checked PCam download.

Full PCam download is NEVER triggered automatically. It requires BOTH the
MEDRISK_ALLOW_DATA_DOWNLOAD=1 environment variable AND an explicit `--download` CLI flag.
The actual HTTP fetch (and "is what's on disk already valid" check) is delegated to
`torchvision.datasets.PCAM` - this module only adds the safety gate and disk-space check
in front of it.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from torchvision.datasets import PCAM

from medrisk_ml.constants import ALLOW_DATA_DOWNLOAD_ENV_VAR
from medrisk_ml.utils.logging import get_logger

logger = get_logger(__name__)

# Rough size of the official PCam HDF5 distribution (train+valid+test, x+y combined).
# Used only for the pre-download warning; the real mirror's exact size can vary slightly.
ESTIMATED_PCAM_SIZE_GB = 7.0
MINIMUM_FREE_SPACE_MULTIPLIER = 2.0


class PCamGateStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    BLOCKED_BY_ENV = "blocked_by_env"
    BLOCKED_BY_SPACE = "blocked_by_space"
    PRECONDITIONS_SATISFIED = "preconditions_satisfied"


@dataclass(frozen=True)
class DownloadDecision:
    status: PCamGateStatus
    message: str
    free_space_gb: float | None = None


def _env_allows_download() -> bool:
    return os.environ.get(ALLOW_DATA_DOWNLOAD_ENV_VAR) == "1"


def check_download_preconditions(data_dir: Path, requested: bool) -> DownloadDecision:
    """Decide whether a real download may proceed, without performing it."""
    if not requested:
        return DownloadDecision(
            PCamGateStatus.NOT_REQUESTED, "Download not requested (pass --download to request it)."
        )
    if not _env_allows_download():
        return DownloadDecision(
            PCamGateStatus.BLOCKED_BY_ENV,
            f"Download blocked: set {ALLOW_DATA_DOWNLOAD_ENV_VAR}=1 to allow downloading the real PCam dataset "
            f"(~{ESTIMATED_PCAM_SIZE_GB:.0f} GB).",
        )
    data_dir.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(data_dir).free
    free_gb = free_bytes / (1024**3)
    required_gb = ESTIMATED_PCAM_SIZE_GB * MINIMUM_FREE_SPACE_MULTIPLIER
    if free_gb < required_gb:
        return DownloadDecision(
            PCamGateStatus.BLOCKED_BY_SPACE,
            f"Download blocked: only {free_gb:.1f} GB free at {data_dir}, need at least "
            f"{required_gb:.1f} GB headroom for a ~{ESTIMATED_PCAM_SIZE_GB:.0f} GB dataset.",
            free_space_gb=free_gb,
        )
    return DownloadDecision(
        PCamGateStatus.PRECONDITIONS_SATISFIED,
        f"Preconditions satisfied ({free_gb:.1f} GB free) - proceeding with download/verification.",
        free_space_gb=free_gb,
    )


def pcam_is_available(data_dir: Path) -> bool:
    """Best-effort presence/integrity check, delegated to torchvision's own loader rather
    than guessing its internal on-disk filenames.
    """
    try:
        PCAM(root=str(data_dir), split="test", download=False)
    except Exception:
        return False
    return True


def ensure_pcam(data_dir: Path, download_requested: bool) -> DownloadDecision:
    """Ensure PCam is available at `data_dir`, downloading only when explicitly allowed."""
    decision = check_download_preconditions(data_dir, download_requested)
    if decision.status != PCamGateStatus.PRECONDITIONS_SATISFIED:
        logger.warning(decision.message)
        return decision

    logger.info("Downloading/verifying PCam at %s ...", data_dir)
    for split in ("train", "val", "test"):
        PCAM(root=str(data_dir), split=split, download=True)
    logger.info("PCam download/verification complete at %s", data_dir)
    return decision

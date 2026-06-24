"""Schemas for the experiment registry (JSONL rows) and the model registry (manifest.json).

A synthetic smoke model must never be indistinguishable from a real candidate model -
`synthetic_only` and `eligible_for_demo` are both explicit, and `ModelRegistry.register`
(registry.py) refuses to accept a manifest where both are true at once.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from medrisk_ml.constants import MEDICAL_DISCLAIMER


class ExperimentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    name: str
    architecture: str
    dataset: str
    dataset_mode: Literal["synthetic", "pcam"]
    status: Literal["running", "completed", "failed"]
    started_at: str
    completed_at: str | None = None
    best_epoch: int | None = None
    best_validation_metric: float | None = None
    selected_threshold: float | None = None
    test_metrics_available: bool = False
    artifact_path: str
    config_hash: str
    git_commit: str | None = None


class ModelManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str
    model_name: str
    model_version: str
    architecture: str
    checkpoint_sha256: str
    dataset_name: str
    dataset_version: str
    dataset_mode: Literal["synthetic", "pcam"]
    input_height: int
    input_width: int
    input_channels: int
    class_names: tuple[str, str]
    positive_class: str
    normalization: dict[str, Any]
    threshold: float
    review_policy: dict[str, Any] | None
    calibration: dict[str, Any] | None
    validation_metrics: dict[str, Any]
    test_metrics: dict[str, Any] | None
    git_commit: str | None
    created_at: str
    medical_disclaimer: str = MEDICAL_DISCLAIMER
    eligible_for_demo: bool
    synthetic_only: bool

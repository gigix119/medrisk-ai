"""Formal research-study specification (Phase 7, master-spec section 7).

`StudyConfig` is the full, strongly-typed, hashable configuration for one research study -
authored as YAML under `research/studies/*.yaml`, loaded and validated by
`medrisk_research.cli`, then persisted as JSONB on `ResearchStudy.configuration` alongside a
SHA-256 hash of its canonical form (`ResearchStudy.configuration_hash`, see
`app.research.domain.hashing.config_hash`).

Validation here is structural, not just descriptive: `EvaluationSpec` rejects a configuration
that would fit calibration or tune a decision threshold against the test split (both the
`Literal["val"]` field types and the explicit `reject_test_split_fitting` call below enforce
this - the former at parse time, the latter so the same guard is reusable by code that
receives a raw split-name string before any schema has validated it, e.g. a CLI flag).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.research.domain.enums import ScientificMaturity, StudyStatus
from app.research.domain.policy import reject_test_split_fitting

SplitStrategy = Literal["predefined", "random", "grouped"]
ThresholdStrategyName = Literal["fixed", "youden_j", "max_f1", "target_sensitivity"]


class DatasetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_slug: str
    dataset_version: str
    manifest_hash: str | None = None
    provenance_classification: str | None = None
    task_type: str
    target_classes: list[str] = Field(min_length=1)
    positive_class: str | None = None
    negative_class: str | None = None
    inclusion_rules: str | None = None
    exclusion_rules: str | None = None
    split_strategy: SplitStrategy = "predefined"
    train_split: str = "train"
    validation_split: str = "val"
    test_split: str = "test"
    external_test_split: str | None = None
    grouping_identifier: str | None = None
    random_seed: int = 42


class PreprocessingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_width: int
    input_height: int
    color_mode: Literal["rgb", "grayscale"] = "rgb"
    normalization_strategy: str
    normalization_stats_source: str | None = None
    interpolation_method: str | None = None
    preprocessing_version: str = "1.0.0"
    augmentation_enabled_for_training: bool = True


class TrainingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    architecture: str
    architecture_version: str | None = None
    pretrained_weights_source: str | None = None
    loss_function: str
    class_weighting: str | None = None
    optimizer: str
    learning_rate: float
    scheduler: str | None = None
    batch_size: int
    epochs: int
    early_stopping_patience: int | None = None
    checkpoint_selection_metric: str
    checkpoint_selection_direction: Literal["max", "min"] = "max"
    mixed_precision: bool = False
    seed: int = 42
    deterministic: bool = True


class EvaluationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_split: Literal["val", "test", "external_test"]
    primary_metric: str
    secondary_metrics: list[str] = Field(default_factory=list)
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    bootstrap_iterations: int = Field(default=1000, ge=0)
    bootstrap_seed: int = 42
    calibration_enabled: bool = False
    # Literal["val"]: structurally the only split calibration may ever be fit on.
    calibration_fit_split: Literal["val"] = "val"
    threshold_strategy: ThresholdStrategyName = "fixed"
    threshold_fit_split: Literal["val"] = "val"
    target_sensitivity: float | None = Field(default=None, gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def _enforce_split_protocol(self) -> EvaluationSpec:
        if self.calibration_enabled:
            reject_test_split_fitting(purpose="Calibration", split_name=self.calibration_fit_split)
        if self.threshold_strategy != "fixed":
            reject_test_split_fitting(
                purpose="Threshold selection", split_name=self.threshold_fit_split
            )
        return self


class GovernanceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intended_use: str
    out_of_scope_use: str
    known_limitations: str
    ethical_considerations: str | None = None
    license_notes: str | None = None
    citation_references: list[str] = Field(default_factory=list)
    scientific_maturity: ScientificMaturity = ScientificMaturity.UNKNOWN


class StudyConfig(BaseModel):
    """Top-level, hashable research-study specification - one YAML file under
    `research/studies/` maps to exactly one of these."""

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    title: str
    short_description: str | None = None
    research_question: str
    hypothesis: str | None = None
    author: str | None = None

    dataset: DatasetSpec
    preprocessing: PreprocessingSpec
    training: TrainingSpec
    evaluation: EvaluationSpec
    governance: GovernanceSpec


class StudyRead(BaseModel):
    """API-facing view of a persisted `ResearchStudy` row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    research_question: str
    hypothesis: str | None
    status: StudyStatus
    scientific_maturity: ScientificMaturity
    dataset_id: uuid.UUID | None
    dataset_version: str | None
    configuration: dict
    configuration_hash: str
    created_at: datetime
    updated_at: datetime


class StudyValidationResult(BaseModel):
    """Result of re-validating a study's stored configuration against the current
    `StudyConfig` schema - never mutates the stored row."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    configuration_hash: str | None = None

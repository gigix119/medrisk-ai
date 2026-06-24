"""Typed, validated experiment configuration.

Every experiment is defined by a YAML file matching `ExperimentConfig` below, optionally
patched with `--set section.key=value` CLI overrides. Unknown keys (in the YAML file or in
an override) are always a hard error - `extra="forbid"` on every section means a typo never
silently does nothing.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from medrisk_ml.constants import REPO_ROOT
from medrisk_ml.utils.hashing import stable_hash


class ConfigError(ValueError):
    """Raised when a YAML experiment config (or a CLI override) fails validation."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ExperimentSection(_StrictModel):
    name: str
    description: str = ""
    seed: int = 42
    output_dir: str = "artifacts/experiments"
    tags: list[str] = Field(default_factory=list)


class DataSection(_StrictModel):
    dataset_name: Literal["pcam", "synthetic"] = "synthetic"
    data_dir: str = "data/external/pcam"
    download: bool = False
    synthetic: bool = True
    smoke_mode: bool = False
    train_subset_size: int | None = None
    validation_subset_size: int | None = None
    test_subset_size: int | None = None
    image_size: int = 96
    num_workers: int = 0
    pin_memory: bool = False
    persistent_workers: bool = False
    prefetch_factor: int | None = None

    @field_validator("image_size")
    @classmethod
    def _positive_image_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("data.image_size must be positive")
        return v

    @field_validator("num_workers")
    @classmethod
    def _non_negative_workers(cls, v: int) -> int:
        if v < 0:
            raise ValueError("data.num_workers must be >= 0")
        return v

    @field_validator("train_subset_size", "validation_subset_size", "test_subset_size")
    @classmethod
    def _positive_subset_size(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("data subset sizes must be positive when set")
        return v

    @model_validator(mode="after")
    def _cross_field_checks(self) -> DataSection:
        expected_synthetic = self.dataset_name == "synthetic"
        if self.synthetic != expected_synthetic:
            raise ValueError(
                f"data.synthetic must be {expected_synthetic} when "
                f"data.dataset_name={self.dataset_name!r}"
            )
        if self.persistent_workers and self.num_workers == 0:
            raise ValueError("data.persistent_workers requires data.num_workers > 0")
        if self.prefetch_factor is not None and self.num_workers == 0:
            raise ValueError("data.prefetch_factor requires data.num_workers > 0")
        return self


class ModelSection(_StrictModel):
    architecture: Literal["baseline_cnn", "resnet18"] = "baseline_cnn"
    pretrained: bool = False
    num_classes: int = 1
    dropout: float = 0.3
    freeze_backbone: bool = False
    unfreeze_from_layer: str | None = None

    @field_validator("dropout")
    @classmethod
    def _valid_dropout(cls, v: float) -> float:
        if not 0.0 <= v < 1.0:
            raise ValueError("model.dropout must be in [0, 1)")
        return v

    @field_validator("num_classes")
    @classmethod
    def _binary_only(cls, v: int) -> int:
        if v != 1:
            raise ValueError(
                "Only binary classification (num_classes=1, single logit output) is "
                "supported in Phase 2"
            )
        return v

    @model_validator(mode="after")
    def _architecture_consistency(self) -> ModelSection:
        if self.architecture == "baseline_cnn" and self.pretrained:
            raise ValueError(
                "model.pretrained=true is not supported for architecture='baseline_cnn'"
            )
        if self.architecture == "baseline_cnn" and self.unfreeze_from_layer is not None:
            raise ValueError("model.unfreeze_from_layer only applies to architecture='resnet18'")
        return self


class TrainingSection(_StrictModel):
    epochs: int = 1
    batch_size: int = 16
    learning_rate: float = 1e-3
    weight_decay: float = 0.0
    optimizer: Literal["adamw", "sgd"] = "adamw"
    scheduler: Literal["reduce_on_plateau", "cosine", "none"] = "none"
    warmup_epochs: int = 0
    mixed_precision: bool = False
    gradient_clip_norm: float | None = None
    accumulation_steps: int = 1
    early_stopping_patience: int = 5
    monitored_metric: str = "roc_auc"
    monitored_mode: Literal["min", "max"] = "max"

    @field_validator("epochs")
    @classmethod
    def _positive_epochs(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("training.epochs must be positive")
        return v

    @field_validator("batch_size")
    @classmethod
    def _positive_batch_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("training.batch_size must be positive")
        return v

    @field_validator("learning_rate")
    @classmethod
    def _positive_lr(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("training.learning_rate must be positive")
        return v

    @field_validator("weight_decay")
    @classmethod
    def _non_negative_weight_decay(cls, v: float) -> float:
        if v < 0:
            raise ValueError("training.weight_decay must be >= 0")
        return v

    @field_validator("warmup_epochs")
    @classmethod
    def _non_negative_warmup(cls, v: int) -> int:
        if v < 0:
            raise ValueError("training.warmup_epochs must be >= 0")
        return v

    @field_validator("accumulation_steps")
    @classmethod
    def _positive_accumulation(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("training.accumulation_steps must be positive")
        return v

    @field_validator("early_stopping_patience")
    @classmethod
    def _non_negative_patience(cls, v: int) -> int:
        if v < 0:
            raise ValueError("training.early_stopping_patience must be >= 0")
        return v

    @field_validator("gradient_clip_norm")
    @classmethod
    def _positive_clip_norm(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("training.gradient_clip_norm must be positive when set")
        return v


class EvaluationSection(_StrictModel):
    default_threshold: float = 0.5
    threshold_strategy: Literal["fixed", "youden_j", "max_f1", "target_sensitivity"] = "fixed"
    target_sensitivity: float | None = None
    calibration: bool = False
    bootstrap_samples: int = 0
    confidence_level: float = 0.95

    @field_validator("default_threshold")
    @classmethod
    def _valid_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("evaluation.default_threshold must be in [0, 1]")
        return v

    @field_validator("confidence_level")
    @classmethod
    def _valid_confidence(cls, v: float) -> float:
        if not 0.0 < v < 1.0:
            raise ValueError("evaluation.confidence_level must be in (0, 1)")
        return v

    @field_validator("bootstrap_samples")
    @classmethod
    def _non_negative_bootstrap(cls, v: int) -> int:
        if v < 0:
            raise ValueError("evaluation.bootstrap_samples must be >= 0")
        return v

    @model_validator(mode="after")
    def _target_sensitivity_consistency(self) -> EvaluationSection:
        if self.threshold_strategy == "target_sensitivity" and self.target_sensitivity is None:
            raise ValueError(
                "evaluation.target_sensitivity is required when "
                "threshold_strategy='target_sensitivity'"
            )
        if self.target_sensitivity is not None and not 0.0 < self.target_sensitivity < 1.0:
            raise ValueError("evaluation.target_sensitivity must be in (0, 1)")
        return self


class LoggingSection(_StrictModel):
    log_level: str = "INFO"
    tensorboard: bool = True
    save_predictions: bool = True


class RuntimeSection(_StrictModel):
    device: Literal["auto", "cuda", "mps", "cpu"] = "auto"
    deterministic: bool = False
    benchmark: bool = True

    @model_validator(mode="after")
    def _deterministic_benchmark_conflict(self) -> RuntimeSection:
        if self.deterministic and self.benchmark:
            raise ValueError("runtime.benchmark must be false when runtime.deterministic is true")
        return self


class ExperimentConfig(_StrictModel):
    experiment: ExperimentSection
    data: DataSection
    model: ModelSection
    training: TrainingSection
    evaluation: EvaluationSection = Field(default_factory=EvaluationSection)
    logging: LoggingSection = Field(default_factory=LoggingSection)
    runtime: RuntimeSection = Field(default_factory=RuntimeSection)


@dataclass(frozen=True)
class LoadedConfig:
    """A validated config plus the bookkeeping needed to reproduce/identify the run."""

    config: ExperimentConfig
    config_hash: str
    source_path: Path
    overrides: tuple[str, ...]
    resolved_output_dir: Path
    resolved_data_dir: Path


def apply_overrides(raw: dict[str, Any], overrides: list[str]) -> dict[str, Any]:
    """Apply `section.key=value` overrides to a raw (pre-validation) config dict.

    Values are parsed with `yaml.safe_load`, so `16` -> int, `0.001` -> float,
    `true` -> bool, `null` -> None, and anything else stays a string - the same
    scalar rules YAML itself uses, applied consistently to CLI overrides.
    """
    result = copy.deepcopy(raw)
    for item in overrides:
        if "=" not in item:
            raise ConfigError(f"Invalid override (expected section.key=value): {item!r}")
        key_path, raw_value = item.split("=", 1)
        if not key_path:
            raise ConfigError(f"Invalid override (empty key path): {item!r}")
        value = yaml.safe_load(raw_value)
        keys = key_path.split(".")
        cursor = result
        for key in keys[:-1]:
            cursor = cursor.setdefault(key, {})
        cursor[keys[-1]] = value
    return result


def _resolve_path(value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (REPO_ROOT / candidate).resolve()


def load_config(path: Path | str, overrides: list[str] | None = None) -> LoadedConfig:
    """Load, override, and validate an experiment YAML config.

    Raises `FileNotFoundError` if the file is missing and `ConfigError` for any
    validation failure (missing required field, unknown key, invalid value, ...).
    """
    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Config file not found: {source_path}")

    with source_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ConfigError(f"Top-level config in {source_path} must be a mapping")

    override_list = overrides or []
    merged = apply_overrides(raw, override_list) if override_list else raw

    try:
        config = ExperimentConfig.model_validate(merged)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration in {source_path}:\n{exc}") from exc

    config_hash = stable_hash(config.model_dump(mode="json"))

    return LoadedConfig(
        config=config,
        config_hash=config_hash,
        source_path=source_path,
        overrides=tuple(override_list),
        resolved_output_dir=_resolve_path(config.experiment.output_dir),
        resolved_data_dir=_resolve_path(config.data.data_dir),
    )

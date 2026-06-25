"""Unit tests for app.research.schemas.study.StudyConfig - no DB, no app.

The split-protocol guard is enforced two ways: structurally, by `Literal["val"]` on
`calibration_fit_split`/`threshold_fit_split` (rejected at parse time, before
`reject_test_split_fitting` even runs), and by the explicit `model_validator` calling
`reject_test_split_fitting` for the same purpose elsewhere in the codebase. These tests pin
both layers so a future refactor can't quietly drop either one.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.research.schemas.study import StudyConfig


def _minimal_config(**overrides: object) -> dict[str, object]:
    config: dict[str, object] = {
        "slug": "unit-test-study",
        "title": "Unit test study",
        "research_question": "Does the schema validate correctly?",
        "dataset": {
            "dataset_slug": "synthetic-histopathology-demo",
            "dataset_version": "1.0.0",
            "task_type": "binary_classification",
            "target_classes": ["negative", "positive"],
            "positive_class": "positive",
        },
        "preprocessing": {
            "input_width": 96,
            "input_height": 96,
            "normalization_strategy": "per_dataset_mean_std",
        },
        "training": {
            "architecture": "baseline_cnn",
            "loss_function": "binary_cross_entropy",
            "optimizer": "adamw",
            "learning_rate": 0.001,
            "batch_size": 16,
            "epochs": 2,
            "checkpoint_selection_metric": "roc_auc",
        },
        "evaluation": {
            "evaluation_split": "test",
            "primary_metric": "roc_auc",
        },
        "governance": {
            "intended_use": "Testing.",
            "out_of_scope_use": "Not for real use.",
            "known_limitations": "None beyond being a test fixture.",
        },
    }
    config.update(overrides)
    return config


def test_minimal_valid_config_parses() -> None:
    config = StudyConfig.model_validate(_minimal_config())
    assert config.slug == "unit-test-study"
    assert config.evaluation.calibration_fit_split == "val"
    assert config.evaluation.threshold_strategy == "fixed"


def test_unknown_top_level_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        StudyConfig.model_validate(_minimal_config(unexpected_field="oops"))


def test_invalid_slug_format_is_rejected() -> None:
    with pytest.raises(ValidationError):
        StudyConfig.model_validate(_minimal_config(slug="Not Valid Slug!"))


def test_calibration_fit_split_cannot_be_test() -> None:
    raw = _minimal_config()
    raw["evaluation"] = {
        **raw["evaluation"],  # type: ignore[dict-item]
        "calibration_enabled": True,
        "calibration_fit_split": "test",
    }
    with pytest.raises(ValidationError):
        StudyConfig.model_validate(raw)


def test_threshold_fit_split_cannot_be_test() -> None:
    raw = _minimal_config()
    raw["evaluation"] = {
        **raw["evaluation"],  # type: ignore[dict-item]
        "threshold_strategy": "max_f1",
        "threshold_fit_split": "test",
    }
    with pytest.raises(ValidationError):
        StudyConfig.model_validate(raw)


def test_calibration_on_validation_split_is_allowed() -> None:
    raw = _minimal_config()
    raw["evaluation"] = {
        **raw["evaluation"],  # type: ignore[dict-item]
        "calibration_enabled": True,
        "calibration_fit_split": "val",
    }
    config = StudyConfig.model_validate(raw)
    assert config.evaluation.calibration_enabled is True


def test_scientific_maturity_defaults_to_unknown() -> None:
    config = StudyConfig.model_validate(_minimal_config())
    assert config.governance.scientific_maturity.value == "unknown"

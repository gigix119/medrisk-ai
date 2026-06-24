from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from medrisk_ml.config import ConfigError, load_config


def _write_config(tmp_path: Path, data: dict[str, Any], name: str = "config.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_valid_config_loads(minimal_config_path: Path) -> None:
    loaded = load_config(minimal_config_path)
    assert loaded.config.experiment.name == "unit-test"
    assert loaded.config.model.architecture == "baseline_cnn"
    assert loaded.config.training.epochs == 1


def test_missing_required_field_fails(tmp_path: Path, minimal_config_dict: dict[str, Any]) -> None:
    broken = copy.deepcopy(minimal_config_dict)
    del broken["experiment"]["name"]
    path = _write_config(tmp_path, broken)
    with pytest.raises(ConfigError):
        load_config(path)


def test_unknown_top_level_field_fails(tmp_path: Path, minimal_config_dict: dict[str, Any]) -> None:
    broken = copy.deepcopy(minimal_config_dict)
    broken["totally_unknown_section"] = {"x": 1}
    path = _write_config(tmp_path, broken)
    with pytest.raises(ConfigError):
        load_config(path)


def test_unknown_nested_field_fails(tmp_path: Path, minimal_config_dict: dict[str, Any]) -> None:
    broken = copy.deepcopy(minimal_config_dict)
    broken["training"]["not_a_real_key"] = 123
    path = _write_config(tmp_path, broken)
    with pytest.raises(ConfigError):
        load_config(path)


def test_invalid_threshold_fails(tmp_path: Path, minimal_config_dict: dict[str, Any]) -> None:
    broken = copy.deepcopy(minimal_config_dict)
    broken["evaluation"] = {"default_threshold": 1.5}
    path = _write_config(tmp_path, broken)
    with pytest.raises(ConfigError):
        load_config(path)


def test_invalid_epoch_count_fails(tmp_path: Path, minimal_config_dict: dict[str, Any]) -> None:
    broken = copy.deepcopy(minimal_config_dict)
    broken["training"]["epochs"] = 0
    path = _write_config(tmp_path, broken)
    with pytest.raises(ConfigError):
        load_config(path)


def test_negative_epoch_count_fails(tmp_path: Path, minimal_config_dict: dict[str, Any]) -> None:
    broken = copy.deepcopy(minimal_config_dict)
    broken["training"]["epochs"] = -3
    path = _write_config(tmp_path, broken)
    with pytest.raises(ConfigError):
        load_config(path)


def test_override_changes_value(minimal_config_path: Path) -> None:
    loaded = load_config(minimal_config_path, overrides=["training.epochs=5"])
    assert loaded.config.training.epochs == 5


def test_override_unknown_key_still_rejected(minimal_config_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(minimal_config_path, overrides=["training.not_a_real_key=5"])


def test_config_hash_is_stable(minimal_config_path: Path) -> None:
    first = load_config(minimal_config_path)
    second = load_config(minimal_config_path)
    assert first.config_hash == second.config_hash


def test_config_hash_differs_for_different_config(minimal_config_path: Path) -> None:
    baseline = load_config(minimal_config_path)
    overridden = load_config(minimal_config_path, overrides=["training.epochs=99"])
    assert baseline.config_hash != overridden.config_hash


def test_deterministic_benchmark_conflict_rejected(
    tmp_path: Path, minimal_config_dict: dict[str, Any]
) -> None:
    broken = copy.deepcopy(minimal_config_dict)
    broken["runtime"] = {"deterministic": True, "benchmark": True}
    path = _write_config(tmp_path, broken)
    with pytest.raises(ConfigError):
        load_config(path)


def test_target_sensitivity_requires_value(
    tmp_path: Path, minimal_config_dict: dict[str, Any]
) -> None:
    broken = copy.deepcopy(minimal_config_dict)
    broken["evaluation"] = {"threshold_strategy": "target_sensitivity"}
    path = _write_config(tmp_path, broken)
    with pytest.raises(ConfigError):
        load_config(path)

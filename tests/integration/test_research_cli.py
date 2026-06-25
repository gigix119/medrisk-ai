"""Tests for medrisk_research.cli (Phase 7).

Lives under tests/integration (not a separate heavy-deps tree like tests/ml) because, as
documented in medrisk_research/__init__.py, this package's current commands need only
Postgres + PyYAML + stdlib - the same dependency tier as everything else here. PyYAML comes
from requirements-dev.txt only; the live API never imports this package or `yaml`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml
from medrisk_research import cli
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import SeededDataset


def test_parse_optional_float_handles_missing_values() -> None:
    assert cli._parse_optional_float(None) is None
    assert cli._parse_optional_float("") is None
    assert cli._parse_optional_float("None") is None
    assert cli._parse_optional_float("0.5") == 0.5


def test_sha256_file_matches_hashlib_reference(tmp_path: Path) -> None:
    path = tmp_path / "sample.bin"
    content = b"hello world"
    path.write_bytes(content)
    assert cli._sha256_file(path) == hashlib.sha256(content).hexdigest()


def test_find_registry_experiment_record_returns_none_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    assert cli._find_registry_experiment_record("does-not-exist") is None


def test_find_registry_experiment_record_finds_matching_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    registry_path = tmp_path / "artifacts" / "registry" / "experiments.jsonl"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps({"experiment_id": "other", "started_at": "2026-01-01T00:00:00+00:00"})
        + "\n"
        + json.dumps({"experiment_id": "target", "started_at": "2026-02-02T00:00:00+00:00"})
        + "\n",
        encoding="utf-8",
    )
    record = cli._find_registry_experiment_record("target")
    assert record is not None
    assert record["started_at"] == "2026-02-02T00:00:00+00:00"


def test_validate_study_command_accepts_well_formed_yaml(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "study.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "slug": "cli-test-study",
                "title": "CLI test study",
                "research_question": "Does the CLI validate a well-formed config?",
                "dataset": {
                    "dataset_slug": "synthetic-histopathology-demo",
                    "dataset_version": "1.0.0",
                    "task_type": "binary_classification",
                    "target_classes": ["negative", "positive"],
                },
                "preprocessing": {
                    "input_width": 32,
                    "input_height": 32,
                    "normalization_strategy": "per_dataset_mean_std",
                },
                "training": {
                    "architecture": "baseline_cnn",
                    "loss_function": "binary_cross_entropy",
                    "optimizer": "adamw",
                    "learning_rate": 0.001,
                    "batch_size": 16,
                    "epochs": 1,
                    "checkpoint_selection_metric": "roc_auc",
                },
                "evaluation": {"evaluation_split": "test", "primary_metric": "roc_auc"},
                "governance": {
                    "intended_use": "Testing.",
                    "out_of_scope_use": "Not for real use.",
                    "known_limitations": "Test fixture.",
                },
            }
        ),
        encoding="utf-8",
    )
    exit_code = cli.cmd_validate_study(cli.argparse.Namespace(config=str(config_path)))
    assert exit_code == 0
    assert "VALID" in capsys.readouterr().out


def test_validate_study_command_rejects_malformed_yaml(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "study.yaml"
    config_path.write_text(yaml.safe_dump({"slug": "missing-required-fields"}), encoding="utf-8")
    exit_code = cli.cmd_validate_study(cli.argparse.Namespace(config=str(config_path)))
    assert exit_code == 1
    assert "INVALID" in capsys.readouterr().out


async def test_load_study_command_persists_study_for_registered_dataset(
    tmp_path: Path, seeded_dataset: SeededDataset, db_session: AsyncSession
) -> None:
    from app.models.dataset import Dataset

    dataset = await db_session.get(Dataset, seeded_dataset.dataset_id)
    assert dataset is not None
    config_path = tmp_path / "study.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "slug": "cli-loaded-study",
                "title": "CLI-loaded study",
                "research_question": "Does load-study persist a row for a registered dataset?",
                "dataset": {
                    "dataset_slug": dataset.slug,
                    "dataset_version": dataset.version,
                    "task_type": "binary_classification",
                    "target_classes": ["negative", "positive"],
                },
                "preprocessing": {
                    "input_width": 32,
                    "input_height": 32,
                    "normalization_strategy": "per_dataset_mean_std",
                },
                "training": {
                    "architecture": "baseline_cnn",
                    "loss_function": "binary_cross_entropy",
                    "optimizer": "adamw",
                    "learning_rate": 0.001,
                    "batch_size": 16,
                    "epochs": 1,
                    "checkpoint_selection_metric": "roc_auc",
                },
                "evaluation": {"evaluation_split": "test", "primary_metric": "roc_auc"},
                "governance": {
                    "intended_use": "Testing.",
                    "out_of_scope_use": "Not for real use.",
                    "known_limitations": "Test fixture.",
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = await cli._load_study_async(config_path)
    assert exit_code == 0

    from app.research.repositories import study as study_repo

    study = await study_repo.get_by_slug(db_session, "cli-loaded-study")
    assert study is not None
    assert study.dataset_id == seeded_dataset.dataset_id


async def test_load_study_command_fails_for_unregistered_dataset(tmp_path: Path) -> None:
    config_path = tmp_path / "study.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "slug": "cli-orphan-study",
                "title": "Orphan study",
                "research_question": "Does load-study refuse an unregistered dataset?",
                "dataset": {
                    "dataset_slug": "does-not-exist",
                    "dataset_version": "9.9.9",
                    "task_type": "binary_classification",
                    "target_classes": ["negative", "positive"],
                },
                "preprocessing": {
                    "input_width": 32,
                    "input_height": 32,
                    "normalization_strategy": "per_dataset_mean_std",
                },
                "training": {
                    "architecture": "baseline_cnn",
                    "loss_function": "binary_cross_entropy",
                    "optimizer": "adamw",
                    "learning_rate": 0.001,
                    "batch_size": 16,
                    "epochs": 1,
                    "checkpoint_selection_metric": "roc_auc",
                },
                "evaluation": {"evaluation_split": "test", "primary_metric": "roc_auc"},
                "governance": {
                    "intended_use": "Testing.",
                    "out_of_scope_use": "Not for real use.",
                    "known_limitations": "Test fixture.",
                },
            }
        ),
        encoding="utf-8",
    )
    exit_code = await cli._load_study_async(config_path)
    assert exit_code == 1

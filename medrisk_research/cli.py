"""Command-line entrypoint: `python -m medrisk_research.cli <command> ...`.

Run with `requirements-dev.txt` installed (Postgres + stdlib + PyYAML - see the package
docstring for why this doesn't need numpy/sklearn/torch today). Each subcommand is a thin
argparse wrapper around an `async def _..._async(...)` function that does the actual work
against `app.db.session.AsyncSessionLocal`, mirroring `scripts/seed_dataset.py`'s
`asyncio.run(...)` pattern and `medrisk_ml/cli.py`'s thin-wrapper-per-subcommand convention.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.dataset_sample import DatasetSample
from app.models.evaluation import EvaluationSamplePrediction
from app.models.model_deployment import ModelDeployment
from app.repositories import dataset as dataset_repo
from app.research.domain.enums import ResultClassification, RunStatus
from app.research.domain.hashing import config_hash
from app.research.domain.metric_shaping import extract_counts, shape_scalar_metrics
from app.research.repositories import evaluation as evaluation_repo
from app.research.repositories import study as study_repo
from app.research.services import dataset_audit_service, study_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("medrisk_research.cli")

REPO_ROOT = Path(__file__).resolve().parent.parent


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        loaded: dict[str, Any] = yaml.safe_load(fh) or {}
    return loaded


def _read_json(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _parse_optional_float(value: str | None) -> float | None:
    if value is None or value in ("", "None"):
        return None
    return float(value)


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_registry_experiment_record(experiment_id: str) -> dict[str, Any] | None:
    registry_path = REPO_ROOT / "artifacts" / "registry" / "experiments.jsonl"
    if not registry_path.is_file():
        return None
    for line in registry_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record: dict[str, Any] = json.loads(line)
        if record.get("experiment_id") == experiment_id:
            return record
    return None


# --- validate-study / load-study -----------------------------------------------------------


def cmd_validate_study(args: argparse.Namespace) -> int:
    raw = _load_yaml(Path(args.config))
    config, errors = study_service.validate_config(raw)
    if config is None:
        print("INVALID study configuration:")
        for error in errors:
            print(f"  - {error}")
        return 1
    digest = config_hash(config.model_dump(mode="json"))
    print(f"VALID: slug={config.slug!r} configuration_hash={digest}")
    return 0


async def _load_study_async(config_path: Path) -> int:
    raw = _load_yaml(config_path)
    config, errors = study_service.validate_config(raw)
    if config is None:
        print("INVALID study configuration:")
        for error in errors:
            print(f"  - {error}")
        return 1

    async with AsyncSessionLocal() as session:
        dataset = await dataset_repo.get_by_slug(session, config.dataset.dataset_slug)
        if dataset is None or dataset.version != config.dataset.dataset_version:
            print(
                f"ERROR: dataset '{config.dataset.dataset_slug}' version "
                f"'{config.dataset.dataset_version}' is not registered. Run "
                "scripts/seed_dataset.py first."
            )
            return 1
        study = await study_service.upsert_study_from_config(session, config, dataset_id=dataset.id)
        await session.commit()
        print(
            f"Loaded study {study.slug!r} (id={study.id}, "
            f"configuration_hash={study.configuration_hash})"
        )
    return 0


def cmd_load_study(args: argparse.Namespace) -> int:
    return asyncio.run(_load_study_async(Path(args.config)))


# --- quality-audit / leakage-audit ---------------------------------------------------------


async def _quality_audit_async(dataset_slug: str, dataset_version: str) -> int:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        dataset = await dataset_repo.get_by_slug(session, dataset_slug)
        if dataset is None or dataset.version != dataset_version:
            print(f"ERROR: dataset '{dataset_slug}' version '{dataset_version}' not found.")
            return 1
        audit = await dataset_audit_service.run_and_persist_quality_audit(
            session, dataset_id=dataset.id, datasets_root=Path(settings.DATASETS_ROOT)
        )
    print(f"Quality audit: status={audit.status.value} id={audit.id}")
    print(json.dumps(audit.summary, indent=2, default=str))
    return 0 if audit.status.value != "failed" else 1


def cmd_quality_audit(args: argparse.Namespace) -> int:
    return asyncio.run(_quality_audit_async(args.dataset_slug, args.dataset_version))


async def _leakage_audit_async(dataset_slug: str, dataset_version: str) -> int:
    async with AsyncSessionLocal() as session:
        dataset = await dataset_repo.get_by_slug(session, dataset_slug)
        if dataset is None or dataset.version != dataset_version:
            print(f"ERROR: dataset '{dataset_slug}' version '{dataset_version}' not found.")
            return 1
        audit = await dataset_audit_service.run_and_persist_leakage_audit(
            session, dataset_id=dataset.id
        )
    print(f"Leakage audit: status={audit.status.value} id={audit.id}")
    print(json.dumps(audit.summary, indent=2, default=str))
    return 0 if audit.status.value != "failed" else 1


def cmd_leakage_audit(args: argparse.Namespace) -> int:
    return asyncio.run(_leakage_audit_async(args.dataset_slug, args.dataset_version))


# --- ingest-evaluation -----------------------------------------------------------------------


async def _ingest_evaluation_async(args: argparse.Namespace) -> int:
    experiment_dir = REPO_ROOT / "artifacts" / "experiments" / args.experiment_id
    metrics_path = experiment_dir / "metrics" / "metrics.json"
    environment_path = experiment_dir / "environment.json"
    predictions_path = experiment_dir / "predictions" / "test_predictions.csv"
    bundle_dir = REPO_ROOT / "artifacts" / "model_registry" / args.model_id / args.model_version
    manifest_path = bundle_dir / "manifest.json"

    for required in (metrics_path, environment_path, predictions_path, manifest_path):
        if not required.is_file():
            print(f"ERROR: required artifact file not found: {required}")
            return 1

    metrics_raw = _read_json(metrics_path)
    environment_raw = _read_json(environment_path)
    manifest_raw = _read_json(manifest_path)
    registry_record = _find_registry_experiment_record(args.experiment_id)

    class_names: list[str] = list(manifest_raw["class_names"])
    positive_class: str = manifest_raw["positive_class"]
    result_classification = ResultClassification(args.result_classification)

    async with AsyncSessionLocal() as session:
        study = await study_repo.get_by_slug(session, args.study_slug)
        if study is None:
            print(f"ERROR: study '{args.study_slug}' is not loaded yet - run `load-study` first.")
            return 1
        dataset = await dataset_repo.get_by_slug(session, args.dataset_slug)
        if dataset is None or dataset.version != args.dataset_version:
            print(
                f"ERROR: dataset '{args.dataset_slug}' version '{args.dataset_version}' not found."
            )
            return 1

        deployment_result = await session.execute(
            select(ModelDeployment).where(ModelDeployment.model_id == manifest_raw["model_id"])
        )
        model_deployment = deployment_result.scalar_one_or_none()

        started_at = None
        finished_at = None
        if registry_record:
            started_at = datetime.fromisoformat(registry_record["started_at"])
            if registry_record.get("completed_at"):
                finished_at = datetime.fromisoformat(registry_record["completed_at"])

        dirty_note = (
            " Working tree was DIRTY at training time (see environment.json)."
            if environment_raw.get("git_dirty")
            else ""
        )
        experiment_run = await evaluation_repo.create_experiment_run(
            session,
            study_id=study.id,
            run_name=args.experiment_id,
            status=RunStatus.COMPLETED,
            git_commit=environment_raw.get("git_commit"),
            git_dirty=environment_raw.get("git_dirty"),
            configuration_hash=environment_raw.get("config_hash"),
            dataset_manifest_hash=dataset.manifest_hash,
            model_artifact_hash=manifest_raw.get("checkpoint_sha256"),
            seed=environment_raw.get("reproducibility", {}).get("seed"),
            hardware_metadata={
                "device_name": environment_raw.get("device_name"),
                "cuda_available": environment_raw.get("cuda_available"),
                "cuda_version": environment_raw.get("cuda_version"),
                "cudnn_version": environment_raw.get("cudnn_version"),
                "platform": environment_raw.get("platform"),
            },
            software_metadata={
                "python_version": environment_raw.get("python_version"),
                "torch_version": environment_raw.get("torch_version"),
                "torchvision_version": environment_raw.get("torchvision_version"),
            },
            started_at=started_at,
            finished_at=finished_at,
            notes=(
                "Ingested from a pre-existing completed medrisk_ml experiment artifact "
                "(Phase 7 added no new training/evaluation run)." + dirty_note
            ),
            source_artifact_path=str(experiment_dir),
        )

        run = await evaluation_repo.create_pending_evaluation_run(
            session,
            dataset_id=dataset.id,
            model_id=manifest_raw["model_id"],
            model_version=manifest_raw["model_version"],
            split_name=args.split,
            result_classification=result_classification,
            study_id=study.id,
            experiment_run_id=experiment_run.id,
            model_deployment_id=model_deployment.id if model_deployment else None,
        )

        test_metrics = metrics_raw["test_metrics"]
        test_metrics_calibrated = metrics_raw.get("test_metrics_calibrated")
        validation_metrics = metrics_raw.get("validation_metrics")
        temperature = metrics_raw.get("temperature")

        metrics_payload = {
            "class_names": class_names,
            "positive_class": positive_class,
            "scalar_metrics": shape_scalar_metrics(test_metrics),
            "counts": extract_counts(test_metrics),
        }
        calibration_payload: dict[str, Any] | None = None
        if temperature is not None and test_metrics_calibrated is not None:
            calibration_payload = {
                "temperature": temperature,
                "calibrated_scalar_metrics": shape_scalar_metrics(test_metrics_calibrated),
                "calibrated_counts": extract_counts(test_metrics_calibrated),
            }
        threshold_payload = {
            "strategy": metrics_raw.get("threshold_strategy"),
            "threshold": metrics_raw.get("threshold"),
            "target_sensitivity": metrics_raw.get("target_sensitivity"),
            "target_achieved": metrics_raw.get("target_achieved"),
            "validation_scalar_metrics": (
                shape_scalar_metrics(validation_metrics) if validation_metrics else None
            ),
            "validation_counts": (
                extract_counts(validation_metrics) if validation_metrics else None
            ),
        }
        confidence_intervals_payload = metrics_raw.get("bootstrap")

        primary_metric_value = test_metrics.get("roc_auc")
        if isinstance(primary_metric_value, float) and primary_metric_value != primary_metric_value:
            primary_metric_value = None  # NaN -> None; never persisted raw (see metric_shaping)

        artifact_files = {
            "metrics_json": metrics_path,
            "environment_json": environment_path,
            "predictions_csv": predictions_path,
            "report_md": experiment_dir / "report.md",
            "model_manifest_json": manifest_path,
            "model_state": bundle_dir / "model_state.pt",
        }
        artifact_hashes = {
            name: _sha256_file(path) for name, path in artifact_files.items() if path.is_file()
        }
        artifact_manifest = {
            "schema_version": "1.0",
            "evaluation_id": str(run.id),
            "experiment_run_id": str(experiment_run.id),
            "git_commit": environment_raw.get("git_commit"),
            "git_dirty": environment_raw.get("git_dirty"),
            "generated_at": _utc_now().isoformat(),
            "file_sha256": artifact_hashes,
        }
        protocol_payload = {
            "evaluation_split": args.split,
            "threshold_strategy": metrics_raw.get("threshold_strategy"),
            "calibration_enabled": temperature is not None,
        }

        sample_predictions: list[EvaluationSamplePrediction] = []
        unresolved = 0
        with predictions_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                sample_key = row["sample_id"]
                true_label = class_names[int(row["true_label"])]
                predicted_label = class_names[int(row["predicted_label"])]
                uncalibrated = float(row["uncalibrated_probability"])
                calibrated = _parse_optional_float(row.get("calibrated_probability"))
                positive_probability = calibrated if calibrated is not None else uncalibrated
                probabilities = {
                    class_names[0]: round(1.0 - positive_probability, 6),
                    class_names[1]: round(positive_probability, 6),
                }
                is_correct = row["correct"].strip().lower() in ("true", "1")
                error_type = None
                if not is_correct:
                    error_type = (
                        "false_positive" if predicted_label == positive_class else "false_negative"
                    )

                sample_result = await session.execute(
                    select(DatasetSample.id).where(
                        DatasetSample.dataset_id == dataset.id,
                        DatasetSample.sample_key == sample_key,
                    )
                )
                dataset_sample_id = sample_result.scalar_one_or_none()
                if dataset_sample_id is None:
                    unresolved += 1

                sample_predictions.append(
                    EvaluationSamplePrediction(
                        evaluation_run_id=run.id,
                        dataset_sample_id=dataset_sample_id,
                        sample_key=sample_key,
                        split=row["split"],
                        ground_truth_label=true_label,
                        predicted_class=predicted_label,
                        probabilities=probabilities,
                        confidence=round(max(probabilities.values()), 6),
                        is_correct=is_correct,
                        error_type=error_type,
                        inference_duration_ms=None,
                        metadata_json={
                            "uncalibrated_probability": uncalibrated,
                            "calibrated_probability": calibrated,
                            "logit": float(row["logit"]),
                            "threshold": float(row["threshold"]),
                        },
                    )
                )

        await evaluation_repo.bulk_create_sample_predictions(session, sample_predictions)

        notes = (
            f"Ingested {len(sample_predictions)} sample predictions from {predictions_path}; "
            f"{unresolved} of them could not be linked to a Phase 6 dataset_samples row "
            f"(sample_key not found for dataset '{args.dataset_slug}' v{args.dataset_version} "
            '- see docs/PHASE_7_PROGRESS.md, "Important honest finding").'
        )

        await evaluation_repo.mark_evaluation_run_completed(
            session,
            run,
            completed_at=finished_at or _utc_now(),
            primary_metric_name="roc_auc",
            primary_metric_value=primary_metric_value,
            metrics=metrics_payload,
            confidence_intervals=confidence_intervals_payload,
            calibration_metrics=calibration_payload,
            threshold_metrics=threshold_payload,
            artifact_manifest=artifact_manifest,
            protocol_hash=config_hash(protocol_payload),
            notes=notes,
        )
        await session.commit()
        print(f"Ingested evaluation run {run.id} (experiment_run={experiment_run.id}).")
        print(f"  {notes}")
    return 0


def cmd_ingest_evaluation(args: argparse.Namespace) -> int:
    return asyncio.run(_ingest_evaluation_async(args))


# --- argument parsing ------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="medrisk_research", description="MedRisk AI Phase 7 research-platform CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-study", help="Validate a study YAML config against the StudyConfig schema"
    )
    validate_parser.add_argument("--config", required=True)
    validate_parser.set_defaults(func=cmd_validate_study)

    load_parser = subparsers.add_parser(
        "load-study", help="Validate a study YAML config and persist it as a ResearchStudy"
    )
    load_parser.add_argument("--config", required=True)
    load_parser.set_defaults(func=cmd_load_study)

    quality_parser = subparsers.add_parser(
        "quality-audit", help="Run and persist a dataset quality audit"
    )
    quality_parser.add_argument("--dataset-slug", required=True)
    quality_parser.add_argument("--dataset-version", required=True)
    quality_parser.set_defaults(func=cmd_quality_audit)

    leakage_parser = subparsers.add_parser(
        "leakage-audit", help="Run and persist a dataset leakage audit"
    )
    leakage_parser.add_argument("--dataset-slug", required=True)
    leakage_parser.add_argument("--dataset-version", required=True)
    leakage_parser.set_defaults(func=cmd_leakage_audit)

    ingest_parser = subparsers.add_parser(
        "ingest-evaluation",
        help="Ingest a pre-existing completed medrisk_ml experiment as an EvaluationRun",
    )
    ingest_parser.add_argument("--experiment-id", required=True)
    ingest_parser.add_argument("--model-id", required=True, help="Registry model name")
    ingest_parser.add_argument("--model-version", required=True)
    ingest_parser.add_argument("--study-slug", required=True)
    ingest_parser.add_argument("--dataset-slug", required=True)
    ingest_parser.add_argument("--dataset-version", required=True)
    ingest_parser.add_argument("--split", default="test")
    ingest_parser.add_argument(
        "--result-classification",
        default=ResultClassification.SYNTHETIC_DEMO.value,
        choices=[member.value for member in ResultClassification],
    )
    ingest_parser.set_defaults(func=cmd_ingest_evaluation)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    import sys

    sys.exit(main())

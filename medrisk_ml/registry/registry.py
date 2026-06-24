"""Local experiment registry (append-only JSONL) and model registry (validated directories).

No paid experiment tracking - this is the entire tracking system, deliberately simple:
a JSONL file you can `grep`/`pandas.read_json(lines=True)`, and a directory tree you can
`ls`. See docs/ml-architecture.md for how this fits into the rest of the pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path

from medrisk_ml.registry.manifest import ExperimentRecord, ModelManifest
from medrisk_ml.training.checkpointing import load_checkpoint
from medrisk_ml.utils.hashing import sha256_file
from medrisk_ml.utils.logging import get_logger

logger = get_logger(__name__)


class DuplicateExperimentError(ValueError):
    """Raised when appending an experiment_id that is already present in the registry."""


class ModelRegistrationError(ValueError):
    """Raised when a model fails one of the registration preconditions."""


class ExperimentRegistry:
    def __init__(self, registry_path: Path) -> None:
        self.registry_path = registry_path
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    def _existing_ids(self) -> set[str]:
        if not self.registry_path.is_file():
            return set()
        ids: set[str] = set()
        with self.registry_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped:
                    ids.add(json.loads(stripped)["experiment_id"])
        return ids

    def append(self, record: ExperimentRecord) -> None:
        if record.experiment_id in self._existing_ids():
            raise DuplicateExperimentError(
                f"Experiment id already registered: {record.experiment_id}"
            )
        with self.registry_path.open("a", encoding="utf-8") as fh:
            fh.write(record.model_dump_json() + "\n")
        logger.info("Registered experiment %s (status=%s)", record.experiment_id, record.status)

    def all_records(self) -> list[ExperimentRecord]:
        if not self.registry_path.is_file():
            return []
        records: list[ExperimentRecord] = []
        with self.registry_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped:
                    records.append(ExperimentRecord.model_validate_json(stripped))
        return records


class ModelRegistry:
    def __init__(self, registry_root: Path) -> None:
        self.registry_root = registry_root
        self.registry_root.mkdir(parents=True, exist_ok=True)

    def model_dir(self, model_name: str, model_version: str) -> Path:
        return self.registry_root / model_name / model_version

    def register(self, checkpoint_path: Path, manifest: ModelManifest) -> Path:
        """Validate the checkpoint against `manifest` and write manifest.json.

        Preconditions enforced here: checkpoint loads, required metadata/threshold/class
        mapping exist (all checked by `load_checkpoint`), the manifest's declared
        checksum matches the actual file, the version isn't already registered, and a
        synthetic-only model is never also marked eligible for demo. The smoke-inference
        check lives in bundle.py (it needs the exported bundle, not the raw checkpoint).
        """
        target_dir = self.model_dir(manifest.model_name, manifest.model_version)
        if target_dir.exists() and any(target_dir.iterdir()):
            raise ModelRegistrationError(
                f"Model version already registered: {manifest.model_name}/{manifest.model_version}"
            )

        payload = load_checkpoint(checkpoint_path, expected_architecture=manifest.architecture)
        if len(payload.class_names) != 2:
            raise ModelRegistrationError(
                "Checkpoint does not declare a valid 2-class class_names mapping"
            )

        actual_hash = sha256_file(checkpoint_path)
        if actual_hash != manifest.checkpoint_sha256:
            raise ModelRegistrationError(
                f"Checkpoint hash mismatch: manifest says {manifest.checkpoint_sha256}, file is actually {actual_hash}"
            )

        if manifest.synthetic_only and manifest.eligible_for_demo:
            raise ModelRegistrationError("A synthetic_only model cannot be eligible_for_demo")

        target_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = target_dir / "manifest.json"
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        logger.info(
            "Registered model %s/%s at %s", manifest.model_name, manifest.model_version, target_dir
        )
        return manifest_path

    def load_manifest(self, model_name: str, model_version: str) -> ModelManifest:
        manifest_path = self.model_dir(model_name, model_version) / "manifest.json"
        if not manifest_path.is_file():
            raise ModelRegistrationError(f"No manifest found at {manifest_path}")
        return ModelManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

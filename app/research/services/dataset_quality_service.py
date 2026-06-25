"""Reproducible dataset-quality audit (Phase 7, master-spec section 11).

Every check here runs against rows already in Postgres (`DatasetSample`) plus a plain
filesystem walk under `Settings.DATASETS_ROOT` - no numpy/Pillow/torch needed, so this runs
directly inside the live API process (`POST /api/v1/research/datasets/{id}/quality-audit`),
not just offline. Image *decoding* validation (corrupt/truncated pixel data) is out of scope
here on purpose: it would require Pillow, which is not guaranteed present in every API image
variant (see docs/PHASE_7_PROGRESS.md) - this audit checks file existence, non-zero size, and
checksum integrity instead, which together already catch the most common real failure modes
(a sample row pointing at a deleted/moved/corrupted-on-disk file).
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset
from app.models.dataset_sample import DatasetSample
from app.research.domain.enums import AuditStatus, Severity

_CHUNK_SIZE = 1024 * 1024


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_existing_path(dataset_root: Path, relative_path: str) -> Path | None:
    """Same path-traversal containment check as
    `app.services.dataset.resolve_sample_image_path`, but returns `None` for a missing/escaped
    path instead of raising - an audit must enumerate every problem, not stop at the first."""
    candidate = (dataset_root / relative_path).resolve()
    if not candidate.is_relative_to(dataset_root):
        return None
    if not candidate.is_file():
        return None
    return candidate


async def run_quality_audit(
    session: AsyncSession, *, dataset: Dataset, datasets_root: Path
) -> tuple[AuditStatus, dict[str, Any]]:
    result = await session.execute(
        select(DatasetSample).where(DatasetSample.dataset_id == dataset.id)
    )
    samples = list(result.scalars().all())

    findings: list[dict[str, Any]] = []

    def add_finding(code: str, severity: Severity, message: str, **details: Any) -> None:
        findings.append(
            {
                "code": code,
                "severity": severity.value,
                "message": message,
                "details": details or None,
            }
        )

    total_samples = len(samples)
    if total_samples == 0:
        add_finding("EMPTY_DATASET", Severity.CRITICAL, "The dataset has zero registered samples.")

    samples_per_split: Counter[str] = Counter(sample.split for sample in samples)
    samples_per_class: Counter[str] = Counter(sample.ground_truth_label for sample in samples)
    samples_per_class_and_split: Counter[tuple[str, str]] = Counter(
        (sample.split, sample.ground_truth_label) for sample in samples
    )
    dimension_distribution: Counter[tuple[int, int]] = Counter(
        (sample.width, sample.height) for sample in samples
    )
    format_distribution: Counter[str] = Counter(sample.mime_type for sample in samples)

    declared_splits = set(dataset.split_names)
    for split_name in declared_splits:
        if samples_per_split.get(split_name, 0) == 0:
            add_finding(
                "SPLIT_MISSING_SAMPLES",
                Severity.CRITICAL,
                f"Declared split '{split_name}' has zero samples.",
                split=split_name,
            )

    declared_classes = set(dataset.classes)
    unexpected_labels = sorted({s.ground_truth_label for s in samples} - declared_classes)
    if unexpected_labels:
        add_finding(
            "UNEXPECTED_LABEL",
            Severity.CRITICAL,
            "One or more samples have a ground_truth_label outside the dataset's declared classes.",
            labels=unexpected_labels,
        )

    if len(samples_per_class) >= 2:
        counts = sorted(samples_per_class.values())
        imbalance_ratio = counts[-1] / counts[0] if counts[0] > 0 else None
        if imbalance_ratio is not None and imbalance_ratio > 3.0:
            add_finding(
                "CLASS_IMBALANCE",
                Severity.WARNING,
                "Class imbalance ratio (most-common-class count / least-common-class count) "
                "exceeds 3:1.",
                ratio=round(imbalance_ratio, 3),
            )
    else:
        imbalance_ratio = None

    checksum_groups: dict[str, list[str]] = defaultdict(list)
    relative_path_groups: dict[str, list[str]] = defaultdict(list)
    for sample in samples:
        checksum_groups[sample.checksum_sha256].append(sample.sample_key)
        relative_path_groups[sample.relative_path].append(sample.sample_key)

    duplicate_checksums = {k: v for k, v in checksum_groups.items() if len(v) > 1}
    if duplicate_checksums:
        add_finding(
            "DUPLICATE_CHECKSUM",
            Severity.WARNING,
            "Multiple sample rows share an identical file checksum (exact duplicate content).",
            count=len(duplicate_checksums),
        )

    path_collisions = {k: v for k, v in relative_path_groups.items() if len(v) > 1}
    if path_collisions:
        add_finding(
            "PATH_COLLISION",
            Severity.CRITICAL,
            "Multiple sample rows resolve to the same on-disk relative_path.",
            count=len(path_collisions),
        )

    dataset_root = (datasets_root / dataset.slug / dataset.version).resolve()
    images_root = dataset_root / "images"
    missing_files: list[str] = []
    checksum_mismatches: list[str] = []
    registered_relative_paths: set[str] = set()
    for sample in samples:
        registered_relative_paths.add(sample.relative_path)
        resolved = _resolve_existing_path(dataset_root, sample.relative_path)
        if resolved is None:
            missing_files.append(sample.sample_key)
            continue
        if _sha256_file(resolved) != sample.checksum_sha256:
            checksum_mismatches.append(sample.sample_key)

    if missing_files:
        add_finding(
            "MISSING_FILE",
            Severity.CRITICAL,
            "One or more registered samples have no corresponding file on disk.",
            sample_keys=missing_files[:50],
            count=len(missing_files),
        )
    if checksum_mismatches:
        add_finding(
            "CHECKSUM_MISMATCH",
            Severity.CRITICAL,
            "One or more files on disk no longer match their registered checksum.",
            sample_keys=checksum_mismatches[:50],
            count=len(checksum_mismatches),
        )

    orphan_files: list[str] = []
    if images_root.is_dir():
        for path in images_root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(dataset_root).as_posix()
            if relative not in registered_relative_paths:
                orphan_files.append(relative)
    if orphan_files:
        add_finding(
            "ORPHAN_FILE",
            Severity.WARNING,
            "One or more files exist on disk under the dataset's image root but are not "
            "referenced by any registered sample.",
            paths=orphan_files[:50],
            count=len(orphan_files),
        )

    critical_count = sum(1 for f in findings if f["severity"] == Severity.CRITICAL.value)
    warning_count = sum(1 for f in findings if f["severity"] == Severity.WARNING.value)
    if critical_count > 0:
        status = AuditStatus.FAILED
    elif warning_count > 0:
        status = AuditStatus.PASSED_WITH_WARNINGS
    else:
        status = AuditStatus.PASSED

    summary: dict[str, Any] = {
        "total_samples": total_samples,
        "excluded_samples": 0,
        "exclusion_note": (
            "The current dataset registry schema (Phase 6) has no per-sample exclusion flag; "
            "every registered row is treated as included."
        ),
        "samples_per_split": dict(samples_per_split),
        "samples_per_class": dict(samples_per_class),
        "samples_per_class_and_split": {
            f"{split}:{label}": count
            for (split, label), count in samples_per_class_and_split.items()
        },
        "class_imbalance_ratio": imbalance_ratio,
        "class_imbalance_definition": (
            "max(per-class sample count) / min(per-class sample count) across all registered "
            "classes; undefined (null) when fewer than two classes are present."
        ),
        "image_dimension_distribution": {
            f"{w}x{h}": count for (w, h), count in dimension_distribution.items()
        },
        "channel_distribution_note": (
            f"Per-sample channel count is not tracked; the dataset declares "
            f"{dataset.image_channels} channels for all samples."
        ),
        "format_distribution": dict(format_distribution),
        "checksum_coverage": "100% (checksum_sha256 is a required, non-null column)",
        "missing_label_count": 0,
        "missing_label_note": "ground_truth_label is a required, non-null column.",
        "duplicate_checksum_groups": len(duplicate_checksums),
        "path_collision_groups": len(path_collisions),
        "missing_file_count": len(missing_files),
        "checksum_mismatch_count": len(checksum_mismatches),
        "orphan_file_count": len(orphan_files),
        "findings": findings,
        "checks_not_performed": [
            "Image-decode validation (corrupt/truncated pixel data) - requires Pillow, not "
            "guaranteed present in every API image variant.",
        ],
    }

    return status, summary

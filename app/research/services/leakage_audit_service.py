"""Data-leakage audit (Phase 7, master-spec section 12) - exact-overlap detection only.

Implemented checks (all pure SQL/Python over `DatasetSample` rows already in Postgres, no
new dependency):

- **Exact overlap across splits**: identical file checksum, or identical on-disk
  `relative_path`, attributed to samples in two different splits - the strongest possible
  signal that the same physical content was placed in both, say, `train` and `test`.
- **Conflicting labels**: two sample rows with an identical checksum but different
  `ground_truth_label` - a data-integrity problem that would otherwise silently corrupt any
  evaluation.
- **Group-level overlap**: only evaluated when sample `metadata_json` actually carries a
  recognized grouping key (`subject_id`/`patient_id`/`slide_id`/`source_image_id`); when none
  of a dataset's samples carry one, this is reported as genuinely unevaluable - never silently
  skipped or assumed clean.

Not implemented (see docs/PHASE_7_PROGRESS.md "Remaining tasks"): perceptual-hash-based
near-duplicate detection. Pipeline-leakage guarantees (no test-split calibration/threshold
tuning) are enforced as code-level guards elsewhere
(`medrisk_ml.evaluation.thresholding.select_threshold`'s `SplitLeakageError`,
`app.research.domain.policy.reject_test_split_fitting`) and are reported here by reference,
not re-derived from data.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset
from app.models.dataset_sample import DatasetSample
from app.research.domain.enums import AuditStatus, Severity

_GROUPING_KEY_CANDIDATES = ("subject_id", "patient_id", "slide_id", "source_image_id")


async def run_leakage_audit(
    session: AsyncSession, *, dataset: Dataset
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

    checksum_to_samples: dict[str, list[DatasetSample]] = defaultdict(list)
    path_to_samples: dict[str, list[DatasetSample]] = defaultdict(list)
    for sample in samples:
        checksum_to_samples[sample.checksum_sha256].append(sample)
        path_to_samples[sample.relative_path].append(sample)

    cross_split_checksum_overlaps: list[dict[str, Any]] = []
    label_conflicts: list[dict[str, Any]] = []
    for checksum, group in checksum_to_samples.items():
        if len(group) < 2:
            continue
        splits_involved = {s.split for s in group}
        if len(splits_involved) > 1:
            cross_split_checksum_overlaps.append(
                {
                    "checksum_sha256": checksum,
                    "sample_keys": [s.sample_key for s in group],
                    "splits": sorted(splits_involved),
                }
            )
        labels_involved = {s.ground_truth_label for s in group}
        if len(labels_involved) > 1:
            label_conflicts.append(
                {
                    "checksum_sha256": checksum,
                    "sample_keys": [s.sample_key for s in group],
                    "labels": sorted(labels_involved),
                }
            )

    cross_split_path_overlaps: list[dict[str, Any]] = []
    for relative_path, group in path_to_samples.items():
        if len(group) < 2:
            continue
        splits_involved = {s.split for s in group}
        if len(splits_involved) > 1:
            cross_split_path_overlaps.append(
                {
                    "relative_path": relative_path,
                    "sample_keys": [s.sample_key for s in group],
                    "splits": sorted(splits_involved),
                }
            )

    if cross_split_checksum_overlaps:
        add_finding(
            "CROSS_SPLIT_CHECKSUM_OVERLAP",
            Severity.CRITICAL,
            "Identical file content (by checksum) appears in more than one split.",
            count=len(cross_split_checksum_overlaps),
            examples=cross_split_checksum_overlaps[:20],
        )
    if cross_split_path_overlaps:
        add_finding(
            "CROSS_SPLIT_PATH_OVERLAP",
            Severity.CRITICAL,
            "The same on-disk file path is registered under more than one split.",
            count=len(cross_split_path_overlaps),
            examples=cross_split_path_overlaps[:20],
        )
    if label_conflicts:
        add_finding(
            "LABEL_CONFLICT",
            Severity.CRITICAL,
            "Samples with identical file content carry different ground_truth_label values.",
            count=len(label_conflicts),
            examples=label_conflicts[:20],
        )

    group_overlap_evaluable = False
    grouping_key_used: str | None = None
    for key in _GROUPING_KEY_CANDIDATES:
        if any(isinstance(s.metadata_json, dict) and key in s.metadata_json for s in samples):
            group_overlap_evaluable = True
            grouping_key_used = key
            break

    group_overlap_result: dict[str, Any]
    if not group_overlap_evaluable:
        group_overlap_result = {
            "evaluated": False,
            "note": (
                "Subject-level overlap could not be evaluated because the dataset does not "
                "provide a subject identifier."
            ),
        }
        add_finding(
            "GROUP_OVERLAP_NOT_EVALUABLE",
            Severity.WARNING,
            "Subject-level overlap could not be evaluated because the dataset does not "
            "provide a subject identifier.",
        )
    else:
        group_to_splits: dict[str, set[str]] = defaultdict(set)
        for sample in samples:
            if isinstance(sample.metadata_json, dict) and grouping_key_used in sample.metadata_json:
                group_to_splits[str(sample.metadata_json[grouping_key_used])].add(sample.split)
        overlapping_groups = {k: sorted(v) for k, v in group_to_splits.items() if len(v) > 1}
        group_overlap_result = {
            "evaluated": True,
            "grouping_key": grouping_key_used,
            "overlapping_group_count": len(overlapping_groups),
            "examples": dict(list(overlapping_groups.items())[:20]),
        }
        if overlapping_groups:
            add_finding(
                "GROUP_LEVEL_OVERLAP",
                Severity.CRITICAL,
                f"One or more '{grouping_key_used}' values appear in more than one split.",
                count=len(overlapping_groups),
            )

    pipeline_leakage_guards = {
        "test_split_threshold_tuning": {
            "status": "covered_by_code_guard",
            "guard": "medrisk_ml.evaluation.thresholding.select_threshold (raises SplitLeakageError "
            "if split_name='test')",
        },
        "test_split_calibration": {
            "status": "covered_by_code_guard",
            "guard": "app.research.domain.policy.reject_test_split_fitting, enforced structurally by "
            "StudyConfig.EvaluationSpec's Literal['val'] split fields",
        },
        "preprocessing_before_splitting": {
            "status": "not_directly_auditable_from_data",
            "note": "Splits are assigned by the dataset-generation script before any preprocessing "
            "is applied; not independently re-verifiable from registry rows alone.",
        },
    }

    critical_count = sum(1 for f in findings if f["severity"] == Severity.CRITICAL.value)
    warning_count = sum(1 for f in findings if f["severity"] == Severity.WARNING.value)
    if critical_count > 0:
        status = AuditStatus.FAILED
    elif not group_overlap_evaluable:
        status = AuditStatus.INCOMPLETE
    elif warning_count > 0:
        status = AuditStatus.PASSED_WITH_WARNINGS
    else:
        status = AuditStatus.PASSED

    summary: dict[str, Any] = {
        "sample_count": len(samples),
        "cross_split_checksum_overlap_count": len(cross_split_checksum_overlaps),
        "cross_split_path_overlap_count": len(cross_split_path_overlaps),
        "label_conflict_count": len(label_conflicts),
        "group_level_overlap": group_overlap_result,
        "pipeline_leakage_guards": pipeline_leakage_guards,
        "findings": findings,
        "checks_not_performed": [
            "Perceptual-hash near-duplicate detection (pHash/dHash/aHash) - not implemented this "
            "phase; see docs/PHASE_7_PROGRESS.md.",
        ],
    }

    return status, summary

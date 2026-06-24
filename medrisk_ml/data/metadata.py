"""Dataset metadata/integrity inspection: machine- and human-readable reports.

Reports split sizes, class balance, image shape/dtype/value-range, and cheap integrity
signals (unreadable samples, duplicate sample ids) - the kind of thing that should be
checked before trusting any metric computed downstream. Risks called out explicitly:
duplicate samples, split contamination, class imbalance, label noise (not detectable from
metadata alone, but named so a human knows to think about it).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from torch.utils.data import Dataset

from medrisk_ml.types import SplitName


@dataclass
class SplitReport:
    split: str
    num_samples: int
    class_counts: dict[str, int]
    class_proportions: dict[str, float]
    image_height: int
    image_width: int
    channels: int
    dtype: str
    value_min: float
    value_max: float
    unreadable_samples: list[str] = field(default_factory=list)
    duplicate_sample_ids: list[str] = field(default_factory=list)


@dataclass
class DatasetReport:
    dataset_name: str
    generated_at: str
    splits: dict[str, SplitReport]
    risks: list[str]


def inspect_split(
    dataset: Dataset[Any],
    split: SplitName,
    class_names: tuple[str, str],
    max_samples: int | None = None,
) -> SplitReport:
    total_n = len(dataset)  # type: ignore[arg-type]
    sample_n = total_n if max_samples is None else min(max_samples, total_n)

    counts = dict.fromkeys(class_names, 0)
    seen_ids: set[str] = set()
    duplicates: list[str] = []
    unreadable: list[str] = []
    value_min = float("inf")
    value_max = float("-inf")
    height = width = channels = 0
    dtype_name = ""

    for i in range(sample_n):
        try:
            image, label, sample_id = dataset[i]
        except Exception as exc:  # reported in the output, not raised
            unreadable.append(f"index={i} error={exc}")
            continue
        counts[class_names[label]] += 1
        if sample_id in seen_ids:
            duplicates.append(sample_id)
        seen_ids.add(sample_id)
        array = image.detach().cpu().numpy() if hasattr(image, "detach") else np.asarray(image)
        channels, height, width = array.shape
        dtype_name = str(array.dtype)
        value_min = min(value_min, float(array.min()))
        value_max = max(value_max, float(array.max()))

    total = sum(counts.values())
    proportions = {name: (count / total if total else 0.0) for name, count in counts.items()}
    return SplitReport(
        split=split,
        num_samples=sample_n,
        class_counts=counts,
        class_proportions=proportions,
        image_height=height,
        image_width=width,
        channels=channels,
        dtype=dtype_name,
        value_min=value_min if sample_n else 0.0,
        value_max=value_max if sample_n else 0.0,
        unreadable_samples=unreadable,
        duplicate_sample_ids=duplicates,
    )


def build_dataset_report(dataset_name: str, splits: dict[str, SplitReport]) -> DatasetReport:
    risks: list[str] = []
    for name, report in splits.items():
        if report.duplicate_sample_ids:
            risks.append(
                f"{name}: {len(report.duplicate_sample_ids)} duplicate sample id(s) detected"
            )
        if report.unreadable_samples:
            risks.append(f"{name}: {len(report.unreadable_samples)} unreadable sample(s) detected")
        proportions = list(report.class_proportions.values())
        if proportions and max(proportions) > 0.8:
            risks.append(
                f"{name}: class imbalance detected (max class proportion {max(proportions):.2%})"
            )
    if not risks:
        risks.append("No integrity risks detected in the inspected subset.")
    return DatasetReport(
        dataset_name=dataset_name,
        generated_at=datetime.now(UTC).isoformat(),
        splits=splits,
        risks=risks,
    )


def write_dataset_report(report: DatasetReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "dataset_report.json"
    md_path = output_dir / "dataset_report.md"
    json_path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return json_path, md_path


def _render_markdown(report: DatasetReport) -> str:
    lines = [
        f"# Dataset report: {report.dataset_name}",
        "",
        f"Generated at: {report.generated_at}",
        "",
    ]
    for name, split_report in report.splits.items():
        proportions_pct = {k: f"{v:.2%}" for k, v in split_report.class_proportions.items()}
        lines += [
            f"## Split: {name}",
            "",
            f"- Samples inspected: {split_report.num_samples}",
            f"- Class counts: {split_report.class_counts}",
            f"- Class proportions: {proportions_pct}",
            f"- Image shape: {split_report.channels}x{split_report.image_height}x{split_report.image_width} ({split_report.dtype})",
            f"- Value range: [{split_report.value_min:.4f}, {split_report.value_max:.4f}]",
            f"- Unreadable samples: {len(split_report.unreadable_samples)}",
            f"- Duplicate sample ids: {len(split_report.duplicate_sample_ids)}",
            "",
        ]
    lines.append("## Risks")
    lines.append("")
    lines.extend(f"- {risk}" for risk in report.risks)
    lines.append("")
    return "\n".join(lines)

"""Error analysis: surfaces the most informative individual predictions for manual review.

Operates on a per-sample predictions DataFrame with columns: sample_id, true_label,
probability, predicted_label, threshold. Grad-CAM is deliberately not invoked here - see
docs/explainability.md for why a heatmap must never be treated as proof of correctness.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ("sample_id", "true_label", "probability", "predicted_label", "threshold")


def _validate(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"predictions dataframe is missing required column(s): {missing}")


def highest_confidence_false_positives(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    _validate(df)
    mask = (df["predicted_label"] == 1) & (df["true_label"] == 0)
    return df.loc[mask].sort_values("probability", ascending=False).head(top_n)


def highest_confidence_false_negatives(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    _validate(df)
    mask = (df["predicted_label"] == 0) & (df["true_label"] == 1)
    return df.loc[mask].sort_values("probability", ascending=True).head(top_n)


def lowest_confidence_correct_predictions(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    _validate(df)
    correct = df.loc[df["predicted_label"] == df["true_label"]].copy()
    correct["distance_from_threshold"] = (correct["probability"] - correct["threshold"]).abs()
    return correct.sort_values("distance_from_threshold", ascending=True).head(top_n)


def uncertain_predictions(df: pd.DataFrame, band: float = 0.05) -> pd.DataFrame:
    _validate(df)
    distance = (df["probability"] - df["threshold"]).abs()
    return df.loc[distance <= band].sort_values("probability")


def class_specific_error_rates(df: pd.DataFrame) -> pd.DataFrame:
    _validate(df)
    rows = []
    for true_label, group in df.groupby("true_label"):
        n = len(group)
        n_errors = int((group["predicted_label"] != group["true_label"]).sum())
        rows.append(
            {
                "true_label": true_label,
                "n": n,
                "n_errors": n_errors,
                "error_rate": (n_errors / n) if n else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def write_error_analysis(df: pd.DataFrame, output_dir: Path, top_n: int = 10) -> tuple[Path, Path]:
    _validate(df)
    output_dir.mkdir(parents=True, exist_ok=True)
    false_positives = highest_confidence_false_positives(df, top_n)
    false_negatives = highest_confidence_false_negatives(df, top_n)
    low_confidence_correct = lowest_confidence_correct_predictions(df, top_n)
    uncertain = uncertain_predictions(df)
    class_rates = class_specific_error_rates(df)

    combined = pd.concat(
        [
            false_positives.assign(category="highest_confidence_false_positive"),
            false_negatives.assign(category="highest_confidence_false_negative"),
            low_confidence_correct.assign(category="lowest_confidence_correct"),
            uncertain.assign(category="uncertain_near_threshold"),
        ],
        ignore_index=True,
    )
    csv_path = output_dir / "error_analysis.csv"
    combined.to_csv(csv_path, index=False)

    md_path = output_dir / "error_analysis.md"
    md_path.write_text(
        _render_markdown(
            false_positives, false_negatives, low_confidence_correct, uncertain, class_rates
        ),
        encoding="utf-8",
    )
    return csv_path, md_path


def _df_block(df: pd.DataFrame) -> str:
    if len(df) == 0:
        return "(none)"
    return "```text\n" + df.to_string(index=False) + "\n```"


def _render_markdown(
    false_positives: pd.DataFrame,
    false_negatives: pd.DataFrame,
    low_confidence_correct: pd.DataFrame,
    uncertain: pd.DataFrame,
    class_rates: pd.DataFrame,
) -> str:
    lines = [
        "# Error analysis",
        "",
        "## Class-specific error rates",
        "",
        _df_block(class_rates),
        "",
        f"## Highest-confidence false positives (top {len(false_positives)})",
        "",
        _df_block(false_positives),
        "",
        f"## Highest-confidence false negatives (top {len(false_negatives)})",
        "",
        _df_block(false_negatives),
        "",
        f"## Lowest-confidence correct predictions (top {len(low_confidence_correct)})",
        "",
        _df_block(low_confidence_correct),
        "",
        f"## Uncertain predictions near the threshold ({len(uncertain)})",
        "",
        _df_block(uncertain),
        "",
        "Grad-CAM is not used here as proof of correctness - see docs/explainability.md.",
    ]
    return "\n".join(lines)

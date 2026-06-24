"""Final evaluation: freeze threshold/calibration on validation data, then evaluate the
test set exactly once and write predictions/metrics/plots/report.

This is the only place in the codebase that is allowed to look at test-split predictions
for anything other than reporting a final number - see docs/experiment-protocol.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from torch import nn
from torch.utils.data import DataLoader

from medrisk_ml.constants import MEDICAL_DISCLAIMER
from medrisk_ml.evaluation.calibration import apply_calibration, fit_temperature
from medrisk_ml.evaluation.error_analysis import write_error_analysis
from medrisk_ml.evaluation.metrics import compute_binary_metrics, confusion_counts, sigmoid
from medrisk_ml.evaluation.plots import (
    plot_calibration_curve,
    plot_confusion_matrix,
    plot_pr_curve,
    plot_probability_distribution,
    plot_roc_curve,
    plot_threshold_analysis,
)
from medrisk_ml.evaluation.thresholding import ThresholdResult, select_threshold
from medrisk_ml.training.engine import evaluate as run_inference
from medrisk_ml.types import MetricsDict, ThresholdStrategy
from medrisk_ml.utils.device import ResolvedDevice
from medrisk_ml.utils.logging import get_logger

logger = get_logger(__name__)

_BOOTSTRAP_METRICS = ("roc_auc", "pr_auc", "sensitivity", "specificity", "f1")


@dataclass(frozen=True)
class EvaluationResult:
    threshold_result: ThresholdResult
    temperature: float | None
    test_metrics: MetricsDict
    test_metrics_calibrated: MetricsDict | None
    bootstrap: dict[str, Any] | None
    predictions_path: Path
    report_path: Path
    metrics_path: Path
    plot_paths: dict[str, Path]


def bootstrap_ci(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    metric_name: str,
    n_samples: int,
    seed: int,
    confidence_level: float = 0.95,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Bootstrap CI for one metric over repeated resamples of (y_true, y_prob).

    Describes sampling uncertainty for THIS dataset, not full clinical/deployment
    uncertainty - different patients, scanners, or sites are not represented by resampling
    one fixed test set.
    """
    rng = np.random.default_rng(seed)
    n = len(y_true)
    values: list[float] = []
    for _ in range(n_samples):
        indices = rng.integers(0, n, size=n)
        metrics = compute_binary_metrics(y_true[indices], y_prob[indices], threshold)
        value = metrics.get(metric_name)
        if isinstance(value, float) and not np.isnan(value):
            values.append(value)
    if not values:
        return {
            "metric": metric_name,
            "requested_samples": n_samples,
            "successful_samples": 0,
            "lower": None,
            "upper": None,
            "mean": None,
        }
    alpha = 1 - confidence_level
    return {
        "metric": metric_name,
        "requested_samples": n_samples,
        "successful_samples": len(values),
        "lower": float(np.percentile(values, 100 * alpha / 2)),
        "upper": float(np.percentile(values, 100 * (1 - alpha / 2))),
        "mean": float(np.mean(values)),
    }


def run_full_evaluation(
    *,
    model: nn.Module,
    val_loader: DataLoader[Any],
    test_loader: DataLoader[Any],
    loss_fn: nn.Module,
    device: ResolvedDevice,
    output_dir: Path,
    class_names: tuple[str, str],
    threshold_strategy: ThresholdStrategy,
    default_threshold: float = 0.5,
    target_sensitivity: float | None = None,
    calibrate: bool = False,
    bootstrap_samples: int = 0,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> EvaluationResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    val_result = run_inference(model, val_loader, loss_fn, device)
    threshold_result = select_threshold(
        val_result.labels,
        sigmoid(val_result.logits),
        strategy=threshold_strategy,
        split_name="val",
        default_threshold=default_threshold,
        target_sensitivity=target_sensitivity,
    )

    temperature: float | None = None
    if calibrate:
        temperature = fit_temperature(val_result.logits, val_result.labels).temperature

    test_result = run_inference(model, test_loader, loss_fn, device)
    test_probabilities = sigmoid(test_result.logits)
    test_metrics = compute_binary_metrics(
        test_result.labels, test_probabilities, threshold_result.threshold
    )

    test_metrics_calibrated: MetricsDict | None = None
    calibrated_probabilities: np.ndarray | None = None
    if temperature is not None:
        calibrated_probabilities = apply_calibration(test_result.logits, temperature)
        test_metrics_calibrated = compute_binary_metrics(
            test_result.labels, calibrated_probabilities, threshold_result.threshold
        )

    predictions_df = _build_predictions_dataframe(
        test_result.sample_ids,
        test_result.labels,
        test_result.logits,
        test_probabilities,
        calibrated_probabilities,
        threshold_result.threshold,
    )
    predictions_dir = output_dir / "predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = predictions_dir / "test_predictions.csv"
    predictions_df.to_csv(predictions_path, index=False)

    operative_probability_col = (
        "calibrated_probability" if temperature is not None else "uncalibrated_probability"
    )
    error_df = predictions_df.assign(probability=predictions_df[operative_probability_col])
    write_error_analysis(error_df, output_dir / "error_analysis")

    bootstrap_results: dict[str, Any] | None = None
    if bootstrap_samples > 0:
        bootstrap_results = {
            metric_name: bootstrap_ci(
                test_result.labels,
                test_probabilities,
                metric_name,
                bootstrap_samples,
                seed,
                confidence_level,
                threshold_result.threshold,
            )
            for metric_name in _BOOTSTRAP_METRICS
        }

    metrics_dir = output_dir / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = metrics_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "threshold_strategy": threshold_result.strategy,
                "threshold": threshold_result.threshold,
                "target_sensitivity": threshold_result.target_sensitivity,
                "target_achieved": threshold_result.target_achieved,
                "temperature": temperature,
                "validation_metrics": threshold_result.validation_metrics,
                "test_metrics": test_metrics,
                "test_metrics_calibrated": test_metrics_calibrated,
                "bootstrap": bootstrap_results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    plot_paths = _generate_plots(
        test_result.labels,
        test_probabilities,
        calibrated_probabilities,
        threshold_result.threshold,
        class_names,
        output_dir / "plots",
    )

    report_path = output_dir / "report.md"
    _write_report(
        report_path,
        threshold_result,
        temperature,
        test_metrics,
        test_metrics_calibrated,
        bootstrap_results,
        class_names,
    )

    return EvaluationResult(
        threshold_result=threshold_result,
        temperature=temperature,
        test_metrics=test_metrics,
        test_metrics_calibrated=test_metrics_calibrated,
        bootstrap=bootstrap_results,
        predictions_path=predictions_path,
        report_path=report_path,
        metrics_path=metrics_path,
        plot_paths=plot_paths,
    )


def _build_predictions_dataframe(
    sample_ids: list[str],
    labels: np.ndarray,
    logits: np.ndarray,
    uncalibrated_probabilities: np.ndarray,
    calibrated_probabilities: np.ndarray | None,
    threshold: float,
) -> pd.DataFrame:
    labels_int = labels.astype(int)
    predicted_labels = (uncalibrated_probabilities >= threshold).astype(int)
    data: dict[str, Any] = {
        "sample_id": sample_ids,
        "split": "test",
        "true_label": labels_int,
        "logit": logits,
        "uncalibrated_probability": uncalibrated_probabilities,
        "calibrated_probability": (
            calibrated_probabilities
            if calibrated_probabilities is not None
            else [None] * len(sample_ids)
        ),
        "predicted_label": predicted_labels,
        "threshold": threshold,
        "correct": predicted_labels == labels_int,
    }
    return pd.DataFrame(data)


def _generate_plots(
    labels: np.ndarray,
    probabilities: np.ndarray,
    calibrated_probabilities: np.ndarray | None,
    threshold: float,
    class_names: tuple[str, str],
    plots_dir: Path,
) -> dict[str, Path]:
    y_pred = (probabilities >= threshold).astype(int)
    counts = confusion_counts(labels, y_pred)
    paths = {
        "confusion_matrix": plot_confusion_matrix(
            counts, class_names, plots_dir / "confusion_matrix.png"
        ),
        "roc_curve": plot_roc_curve(labels, probabilities, plots_dir / "roc_curve.png"),
        "precision_recall_curve": plot_pr_curve(
            labels, probabilities, plots_dir / "precision_recall_curve.png"
        ),
        "probability_distribution": plot_probability_distribution(
            labels, probabilities, threshold, plots_dir / "probability_distribution.png"
        ),
        "threshold_analysis": plot_threshold_analysis(
            labels, probabilities, plots_dir / "threshold_analysis.png"
        ),
    }
    if calibrated_probabilities is not None:
        paths["calibration_curve"] = plot_calibration_curve(
            labels, probabilities, calibrated_probabilities, plots_dir / "calibration_curve.png"
        )
    return paths


def _write_report(
    report_path: Path,
    threshold_result: ThresholdResult,
    temperature: float | None,
    test_metrics: MetricsDict,
    test_metrics_calibrated: MetricsDict | None,
    bootstrap_results: dict[str, Any] | None,
    class_names: tuple[str, str],
) -> None:
    lines = [
        "# Final evaluation report",
        "",
        f"Classes: {class_names[0]} (negative) / {class_names[1]} (positive)",
        f"Threshold strategy: {threshold_result.strategy} -> threshold={threshold_result.threshold:.4f}",
    ]
    if threshold_result.target_sensitivity is not None:
        lines.append(
            f"Target sensitivity: {threshold_result.target_sensitivity:.3f} "
            f"(achieved: {threshold_result.target_achieved})"
        )
    if temperature is not None:
        lines.append(f"Calibration: temperature scaling, T={temperature:.4f}")
    lines += ["", "## Test metrics (uncalibrated probabilities, frozen threshold)", ""]
    lines += [f"- {key}: {value}" for key, value in test_metrics.items()]
    if test_metrics_calibrated is not None:
        lines += ["", "## Test metrics (calibrated probabilities, same frozen threshold)", ""]
        lines += [f"- {key}: {value}" for key, value in test_metrics_calibrated.items()]
    if bootstrap_results is not None:
        lines += ["", "## Bootstrap confidence intervals (dataset sampling uncertainty only)", ""]
        lines += [f"- {metric_name}: {result}" for metric_name, result in bootstrap_results.items()]
    lines += ["", "---", "", MEDICAL_DISCLAIMER, ""]
    report_path.write_text("\n".join(lines), encoding="utf-8")

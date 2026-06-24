"""Matplotlib-only plotting (no seaborn, no GUI). Each function saves one PNG and closes
its figure - safe to call repeatedly in a long-running process without leaking figures.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # must run before importing pyplot - headless, no GUI backend needed

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import precision_recall_curve, roc_curve

from medrisk_ml.evaluation.calibration import reliability_diagram_bins
from medrisk_ml.evaluation.metrics import ConfusionCounts, compute_binary_metrics


def _save_and_close(fig: plt.Figure, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_training_loss(history: list[dict[str, Any]], output_path: Path) -> Path:
    epochs = [row["epoch"] for row in history]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(epochs, [row["train_loss"] for row in history], marker="o", label="train loss")
    ax.plot(epochs, [row["val_loss"] for row in history], marker="o", label="validation loss")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("BCE loss")
    ax.set_title(f"Training/validation loss (n={len(epochs)} epochs)")
    ax.legend()
    ax.grid(alpha=0.3)
    return _save_and_close(fig, output_path)


def plot_training_metrics(
    history: list[dict[str, Any]], metric_name: str, output_path: Path
) -> Path:
    epochs = [row["epoch"] for row in history]
    train_key, val_key = f"train_{metric_name}", f"val_{metric_name}"
    fig, ax = plt.subplots(figsize=(7, 5))
    if history and train_key in history[0]:
        ax.plot(
            epochs, [row[train_key] for row in history], marker="o", label=f"train {metric_name}"
        )
    if history and val_key in history[0]:
        ax.plot(epochs, [row[val_key] for row in history], marker="o", label=f"val {metric_name}")
    ax.set_xlabel("Epoch")
    ax.set_ylabel(metric_name)
    ax.set_title(f"Training/validation {metric_name}")
    ax.legend()
    ax.grid(alpha=0.3)
    return _save_and_close(fig, output_path)


def plot_confusion_matrix(
    counts: ConfusionCounts, class_names: tuple[str, str], output_path: Path
) -> Path:
    matrix = np.array(
        [
            [counts.true_negative, counts.false_positive],
            [counts.false_negative, counts.true_positive],
        ]
    )
    fig, ax = plt.subplots(figsize=(5, 5))
    im = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks([0, 1], labels=list(class_names))
    ax.set_yticks([0, 1], labels=list(class_names))
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_title(f"Confusion matrix (n={counts.sample_count})")
    half_max = matrix.max() / 2 if matrix.max() else 0
    for i in range(2):
        for j in range(2):
            color = "white" if matrix[i, j] > half_max else "black"
            ax.text(j, i, str(matrix[i, j]), ha="center", va="center", color=color)
    fig.colorbar(im, ax=ax)
    return _save_and_close(fig, output_path)


def plot_roc_curve(y_true: np.ndarray, y_prob: np.ndarray, output_path: Path) -> Path:
    from sklearn.metrics import auc as sklearn_auc

    fpr, tpr, _ = roc_curve(y_true, y_prob)
    auc_value = float(sklearn_auc(fpr, tpr))
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(fpr, tpr, label=f"ROC (AUC={auc_value:.3f}, n={len(y_true)})")
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="chance")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("ROC curve")
    ax.legend()
    ax.grid(alpha=0.3)
    return _save_and_close(fig, output_path)


def plot_pr_curve(y_true: np.ndarray, y_prob: np.ndarray, output_path: Path) -> Path:
    precision, recall, _ = precision_recall_curve(y_true, y_prob)
    positive_rate = float(np.mean(y_true)) if len(y_true) else 0.0
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(recall, precision, label=f"PR curve (n={len(y_true)})")
    ax.axhline(
        positive_rate,
        linestyle="--",
        color="gray",
        label=f"baseline (prevalence={positive_rate:.3f})",
    )
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall curve")
    ax.legend()
    ax.grid(alpha=0.3)
    return _save_and_close(fig, output_path)


def plot_calibration_curve(
    y_true: np.ndarray,
    y_prob_before: np.ndarray,
    y_prob_after: np.ndarray | None,
    output_path: Path,
    n_bins: int = 10,
) -> Path:
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="perfectly calibrated")
    for label, probs in (
        ("before calibration", y_prob_before),
        ("after calibration", y_prob_after),
    ):
        if probs is None:
            continue
        bins = reliability_diagram_bins(y_true, probs, n_bins=n_bins)
        xs = [b.mean_confidence for b in bins if b.count > 0]
        ys = [b.mean_accuracy for b in bins if b.count > 0]
        ax.plot(xs, ys, marker="o", label=label)
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Observed frequency of positive class")
    ax.set_title(f"Calibration curve (n={len(y_true)})")
    ax.legend()
    ax.grid(alpha=0.3)
    return _save_and_close(fig, output_path)


def plot_probability_distribution(
    y_true: np.ndarray, y_prob: np.ndarray, threshold: float, output_path: Path
) -> Path:
    true_arr = np.asarray(y_true)
    prob_arr = np.asarray(y_prob)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(prob_arr[true_arr == 0], bins=20, range=(0, 1), alpha=0.6, label="negative (true)")
    ax.hist(prob_arr[true_arr == 1], bins=20, range=(0, 1), alpha=0.6, label="positive (true)")
    ax.axvline(threshold, color="black", linestyle="--", label=f"threshold={threshold:.3f}")
    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Sample count")
    ax.set_title(f"Predicted probability distribution (n={len(true_arr)})")
    ax.legend()
    return _save_and_close(fig, output_path)


def plot_threshold_analysis(
    y_true: np.ndarray, y_prob: np.ndarray, output_path: Path, num_points: int = 50
) -> Path:
    thresholds = np.linspace(0.01, 0.99, num_points)
    sensitivities: list[float] = []
    specificities: list[float] = []
    precisions: list[float] = []
    for t in thresholds:
        metrics = compute_binary_metrics(y_true, y_prob, float(t))
        sensitivities.append(metrics["sensitivity"])  # type: ignore[arg-type]
        specificities.append(metrics["specificity"])  # type: ignore[arg-type]
        precisions.append(metrics["precision"])  # type: ignore[arg-type]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(thresholds, sensitivities, label="sensitivity")
    ax.plot(thresholds, specificities, label="specificity")
    ax.plot(thresholds, precisions, label="precision")
    ax.set_xlabel("Threshold")
    ax.set_ylabel("Metric value")
    ax.set_title(f"Threshold trade-off analysis (n={len(y_true)})")
    ax.legend()
    ax.grid(alpha=0.3)
    return _save_and_close(fig, output_path)

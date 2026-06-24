"""Temperature scaling: fit on validation logits/labels only, applied to test probabilities.

Temperature scaling (Guo et al., 2017) divides logits by one learned scalar T > 0 before
the sigmoid. Because dividing by a positive constant doesn't change the ranking of
predictions, it can correct over/under-confidence without ever changing ROC-AUC, PR-AUC, or
any other ranking metric - only confidence-sensitive ones like Brier score and expected
calibration error move.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from medrisk_ml.evaluation.metrics import sigmoid


class CalibrationFittingError(ValueError):
    """Raised when temperature fitting is given inappropriate input (e.g. one-class labels)."""


@dataclass(frozen=True)
class CalibrationResult:
    temperature: float
    fitted_on_n_samples: int


def fit_temperature(
    logits: np.ndarray,
    labels: np.ndarray,
    max_iter: int = 100,
    lr: float = 0.01,
) -> CalibrationResult:
    """Fit a single temperature T > 0 minimizing validation BCE, via LBFGS on log(T).

    Optimizing in log-space guarantees T = exp(log_T) > 0 with no extra constraint code.
    """
    logits_arr = np.asarray(logits, dtype=np.float64)
    labels_arr = np.asarray(labels, dtype=np.float64)
    if logits_arr.shape[0] == 0:
        raise CalibrationFittingError("Cannot fit temperature on an empty validation set")
    if len(np.unique(labels_arr)) < 2:
        raise CalibrationFittingError(
            "Cannot fit temperature when validation labels contain only one class"
        )

    logits_t = torch.tensor(logits_arr, dtype=torch.float64)
    labels_t = torch.tensor(labels_arr, dtype=torch.float64)
    log_temperature = torch.zeros(1, dtype=torch.float64, requires_grad=True)
    optimizer = torch.optim.LBFGS([log_temperature], lr=lr, max_iter=max_iter)
    loss_fn = torch.nn.BCEWithLogitsLoss()

    def closure() -> torch.Tensor:
        optimizer.zero_grad()
        temperature = torch.exp(log_temperature)
        loss: torch.Tensor = loss_fn(logits_t / temperature, labels_t)
        loss.backward()
        return loss

    optimizer.step(closure)
    temperature = float(torch.exp(log_temperature).item())
    return CalibrationResult(temperature=temperature, fitted_on_n_samples=int(logits_arr.shape[0]))


def apply_calibration(logits: np.ndarray, temperature: float) -> np.ndarray:
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    return sigmoid(np.asarray(logits, dtype=np.float64) / temperature)


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Mean, bin-count-weighted |accuracy - confidence| over equal-width probability bins."""
    true_arr = np.asarray(y_true, dtype=np.float64)
    prob_arr = np.asarray(y_prob, dtype=np.float64)
    if true_arr.shape[0] == 0:
        return float("nan")
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_indices = np.clip(np.digitize(prob_arr, bin_edges[1:-1]), 0, n_bins - 1)
    ece = 0.0
    n = true_arr.shape[0]
    for bin_index in range(n_bins):
        mask = bin_indices == bin_index
        count = int(np.sum(mask))
        if count == 0:
            continue
        bin_confidence = float(np.mean(prob_arr[mask]))
        bin_accuracy = float(np.mean(true_arr[mask]))
        ece += (count / n) * abs(bin_accuracy - bin_confidence)
    return ece


@dataclass(frozen=True)
class ReliabilityBin:
    bin_lower: float
    bin_upper: float
    count: int
    mean_confidence: float
    mean_accuracy: float


def reliability_diagram_bins(
    y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10
) -> list[ReliabilityBin]:
    true_arr = np.asarray(y_true, dtype=np.float64)
    prob_arr = np.asarray(y_prob, dtype=np.float64)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_indices = np.clip(np.digitize(prob_arr, bin_edges[1:-1]), 0, n_bins - 1)
    bins: list[ReliabilityBin] = []
    for bin_index in range(n_bins):
        mask = bin_indices == bin_index
        count = int(np.sum(mask))
        mean_confidence = float(np.mean(prob_arr[mask])) if count else float("nan")
        mean_accuracy = float(np.mean(true_arr[mask])) if count else float("nan")
        bins.append(
            ReliabilityBin(
                bin_lower=float(bin_edges[bin_index]),
                bin_upper=float(bin_edges[bin_index + 1]),
                count=count,
                mean_confidence=mean_confidence,
                mean_accuracy=mean_accuracy,
            )
        )
    return bins

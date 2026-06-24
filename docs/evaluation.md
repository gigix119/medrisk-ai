# Evaluation

This document explains every metric, plot, and artifact produced by `medrisk_ml.cli evaluate`, and the policy for handling values that are mathematically undefined.

## Metrics (`medrisk_ml/evaluation/metrics.py::compute_binary_metrics`)

All metrics are computed from scratch against numpy arrays (`y_true` ∈ {0,1}, `y_prob` ∈ [0,1]) at one fixed decision threshold — `roc_auc`/`pr_auc` are the only two that are threshold-independent by definition (sklearn's `roc_auc_score`/`average_precision_score` sweep all thresholds internally).

| Metric | Formula | Meaning |
|---|---|---|
| `accuracy` | (TP+TN) / N | Overall fraction correct — misleading alone on imbalanced data |
| `balanced_accuracy` | (sensitivity + specificity) / 2 | Accuracy that weights both classes equally regardless of class balance |
| `precision` | TP / (TP+FP) | Of samples predicted positive, fraction actually positive |
| `recall` / `sensitivity` | TP / (TP+FN) | Of samples actually positive, fraction caught — *the* clinically-loaded number for "missed tumor" risk |
| `specificity` | TN / (TN+FP) | Of samples actually negative, fraction correctly cleared |
| `f1` | 2·precision·recall / (precision+recall) | Harmonic mean of precision and recall |
| `roc_auc` | Area under the ROC curve | Probability a random positive scores higher than a random negative; insensitive to class balance |
| `pr_auc` | Area under the precision-recall curve | More informative than ROC-AUC under class imbalance |
| `brier_score` | mean((prob − label)²) | Calibration-sensitive accuracy — lower is better, rewards confident *and* correct |

### Undefined-metric policy

`precision` is undefined when there are zero positive predictions (`TP+FP=0`); `sensitivity`/`recall` are undefined with zero actual positives; `roc_auc`/`pr_auc` are undefined with only one class present in `y_true`. In every one of these cases, `compute_binary_metrics()` reports **`float("nan")`**, never a silently substituted `0.0` or `1.0` — a `nan` in a report is supposed to make you stop and ask why, not get averaged into a misleadingly clean-looking number. `_safe_div()` is the one helper responsible for this throughout the module.

## Threshold selection and calibration

See [experiment-protocol.md](experiment-protocol.md) for the full leakage-prevention rationale — both are fit on the validation split only, then frozen before test-split inference.

**Temperature scaling** (`medrisk_ml/evaluation/calibration.py::fit_temperature`) learns one scalar `T > 0` (via LBFGS in log-space, so positivity is structural, not enforced by a clamp) minimizing validation BCE when logits are divided by `T` before the sigmoid. Dividing by a positive constant never changes the *ranking* of predictions, so `roc_auc`/`pr_auc` are mathematically identical before and after calibration — only confidence-sensitive metrics (`brier_score`, expected calibration error) can move. `run_full_evaluation()` reports both the uncalibrated and calibrated test metrics side by side specifically so this distinction is visible, not asserted.

**Expected Calibration Error** (`expected_calibration_error()`) bins predictions into `n_bins` equal-width probability bins and computes the bin-count-weighted mean absolute gap between each bin's average confidence and its average accuracy — `reliability_diagram_bins()` returns the same per-bin breakdown for plotting.

## Bootstrap confidence intervals (`medrisk_ml/evaluation/evaluator.py::bootstrap_ci`)

For each of `roc_auc`, `pr_auc`, `sensitivity`, `specificity`, `f1`, the test set is resampled with replacement `evaluation.bootstrap_samples` times; the metric is recomputed each time (skipping any resample that produces `nan`, e.g. a resample with only one class present); the reported interval is the `[2.5, 97.5]` percentile band (or whatever `confidence_level` implies) of the resulting distribution.

> **What this interval does and does not mean.** It quantifies *sampling uncertainty from resampling one fixed test set* — "if I had drawn a slightly different sample of the same size from the same distribution, how much would this number plausibly move." It is **not** clinical or deployment uncertainty: different scanners, staining protocols, hospitals, or patient populations are not represented anywhere in a resample of the same fixed dataset. A narrow bootstrap CI is not evidence of real-world robustness.

## Plots (`medrisk_ml/evaluation/plots.py`)

All written under `<experiment_dir>/plots/`, matplotlib's `Agg` backend (headless, no display required):

| File | Shows |
|---|---|
| `confusion_matrix.png` | TP/TN/FP/FN counts at the frozen threshold |
| `roc_curve.png` | ROC curve + AUC (computed via `sklearn.metrics.auc`, not the deprecated `np.trapz`) |
| `precision_recall_curve.png` | Precision-recall curve + AUC |
| `probability_distribution.png` | Histogram of predicted probabilities, split by true class, with the threshold marked |
| `threshold_analysis.png` | Precision/recall/F1 as a function of threshold — context for why a given threshold was chosen |
| `calibration_curve.png` | Reliability diagram (only generated when `evaluation.calibration: true`) |

## Error analysis (`medrisk_ml/evaluation/error_analysis.py`)

Written to `<experiment_dir>/error_analysis/{error_analysis.csv, error_analysis.md}` — surfaces the individual predictions most worth a human looking at, not just aggregate numbers:

- **Highest-confidence false positives** — the model was *sure* and wrong in the "predicted tumor, wasn't one" direction.
- **Highest-confidence false negatives** — the model was *sure* and wrong in the "predicted clear, was tumor" direction — typically the more clinically concerning failure mode.
- **Lowest-confidence correct predictions** — got it right, but barely; early warning signs of a fragile decision boundary.
- **Uncertain predictions near the threshold** (`|probability − threshold| ≤ 0.05`) — cases where a tiny model or data change would flip the decision.
- **Class-specific error rates** — error rate computed separately per true class, since overall accuracy can hide a model that's much worse on one class than the other.

Grad-CAM is deliberately **not** invoked anywhere in error analysis — see [explainability.md](explainability.md) for why a heatmap is not evidence that a prediction (right or wrong) was reached for the correct reason.

## Output artifacts, per experiment

```text
artifacts/experiments/<experiment_id>/
├── predictions/test_predictions.csv     One row per test sample: logit, both probabilities, prediction, correctness
├── metrics/metrics.json                  Everything above, machine-readable
├── report.md                             Human-readable summary, ends with the medical disclaimer
├── plots/*.png
└── error_analysis/{error_analysis.csv, error_analysis.md}
```

`metrics.json` and `report.md` are the two files `medrisk_ml.cli register` reads from — registering a model without first running `evaluate` fails fast with a clear message rather than registering incomplete metrics.

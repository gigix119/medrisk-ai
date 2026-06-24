# Model card template

Copy this template for every model registered via `medrisk_ml.cli register`. The short, auto-generated `model_card.md` written into the model's bundle (`medrisk_ml/cli.py::_render_model_card`) is a machine-filled *summary* of this template's "Model details" and "Quantitative results" sections only — anything narrative (intended use, caveats, ethical considerations) must be filled in by hand before a model is treated as anything more than an internal experiment.

---

## Model details

- **Model name / version:** `<model_name>:<model_version>`
- **Architecture:** `baseline_cnn` | `resnet18` (see [ml-architecture.md](ml-architecture.md))
- **Date registered:**
- **Git commit:**
- **Config hash:**
- **Trained by:**
- **Synthetic-only:** `true` | `false` — if `true`, this model **must** have `eligible_for_demo: false` (enforced by `ModelRegistry.register`) and every result below must carry the SYNTHETIC DATA warning.

## Intended use

- **Intended use case:** Educational/research portfolio demonstration of a histopathology binary-classification pipeline (PatchCamelyon-style: tumor tissue present/absent in a patch's center region).
- **Out-of-scope uses:** Any clinical, diagnostic, or treatment-related use. Any use on patient data. Any use as a sole or contributing factor in a real medical decision. See the medical disclaimer below — it is not optional framing, it is a hard constraint on how this model may be used.
- **Intended users:** Developers/reviewers evaluating this portfolio project; not clinicians, not patients.

## Training data

- **Dataset:** `<dataset_name>` (`synthetic` | `pcam`), version `<dataset_version>`. See [dataset-card-pcam.md](dataset-card-pcam.md) for the full dataset card, including known biases.
- **Train / val / test sizes:**
- **Class balance per split:** (from `artifacts/dataset_reports/.../dataset_report.json`)
- **Preprocessing:** resize to `<input_height>x<input_width>`, normalization `<normalization>` (either dataset-computed train-split mean/std for `baseline_cnn`, or fixed ImageNet stats for `resnet18`).

## Evaluation protocol

- **Threshold strategy:** `<threshold_strategy>` → frozen threshold `<threshold>` (selected on the **validation** split only — see [experiment-protocol.md](experiment-protocol.md)).
- **Calibration:** temperature scaling, `T=<temperature>` (or "not applied").
- **Test-set evaluation:** performed exactly once, after the threshold and calibration above were already frozen.

## Quantitative results

> If `synthetic_only: true`, prepend: **SYNTHETIC SMOKE EXPERIMENT — NOT A MEDICAL PERFORMANCE RESULT.** These numbers measure only whether the pipeline learns a trivial synthetic task; they say nothing about real diagnostic performance.

| Metric | Validation | Test (uncalibrated) | Test (calibrated) |
|---|---|---|---|
| ROC-AUC | | | (identical to uncalibrated — calibration never changes ranking) |
| PR-AUC | | | (identical to uncalibrated) |
| Sensitivity (recall) | | | |
| Specificity | | | |
| F1 | | | |
| Brier score | | | |

Bootstrap 95% CIs (`bootstrap_samples=<n>`, sampling uncertainty over this one fixed test set only — see [evaluation.md](evaluation.md)):

| Metric | Lower | Mean | Upper |
|---|---|---|---|
| ROC-AUC | | | |
| Sensitivity | | | |
| Specificity | | | |

Full plots, error analysis, and the machine-readable `metrics.json` live in `artifacts/experiments/<experiment_id>/`.

## Explainability

Grad-CAM overlays for representative true-positive / true-negative / false-positive / false-negative / uncertain test samples are in `artifacts/experiments/<experiment_id>/gradcam/`.

> **Grad-CAM highlights regions associated with the model output. It is not a biological explanation and must not be used as a diagnosis.**

See [explainability.md](explainability.md) for what Grad-CAM does and does not demonstrate about this specific model.

## Known limitations and failure modes

- (Fill in from `error_analysis.md`: which class has the higher error rate? What do the highest-confidence mistakes have in common, if anything?)
- Patch-level evaluation only — no slide-level or patient-level aggregation exists in this pipeline.
- No evaluation against any data source other than the one named above — no claim of generalization across scanners, stains, or patient populations is supported.
- (Synthetic models only) Not evaluated against any real tissue image whatsoever.

## Ethical considerations

- No patient-identifying data is used or stored anywhere in this project.
- This model must never be presented, demoed, or deployed in a way that could be mistaken for a clinically validated diagnostic tool.
- A `review_policy` field exists in the manifest for a future human-in-the-loop gating rule (e.g. "always route to human review below sensitivity target X"); leaving it `null` means **no automated review policy is defined or enforced** — that is not a substitute for clinical oversight.

## Medical disclaimer

```
This software is an educational and research portfolio project.
It is not a medical device and must not be used for diagnosis,
treatment decisions, or emergency medical guidance.
```

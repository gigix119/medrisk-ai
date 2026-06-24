# Explainability (Grad-CAM)

> **Grad-CAM highlights regions associated with the model output. It is not a biological explanation and must not be used as a diagnosis.**

This exact sentence is written into every directory of generated overlays (`gradcam/DISCLAIMER.txt`) and must accompany any Grad-CAM image shown anywhere outside this repository.

## What Grad-CAM actually computes

Grad-CAM (Selvaraju et al., 2017) answers one specific, narrow question: *which spatial locations in a chosen convolutional layer's activations, when increased, would most increase (or decrease) this one model output.* Implemented from scratch in [medrisk_ml/explainability/gradcam.py](../medrisk_ml/explainability/gradcam.py) (no third-party Grad-CAM library — small enough to own, audit, and unit-test):

1. A forward hook (`medrisk_ml/explainability/hooks.py::ActivationsAndGradients`) captures the target layer's activation tensor during the forward pass, and a backward hook captures its gradient during backpropagation.
2. Because this is a **binary, single-logit model**, there is no "class index" to choose between the way multi-class Grad-CAM would — backprop always starts from that one logit (`target_sign=1.0`), or its negation (`target_sign=-1.0`, "what pushed the prediction *away* from positive") when explicitly requested.
3. Per-channel weights are the spatial mean of that channel's gradient; the heatmap is the ReLU of the weighted sum of activation channels, upsampled (bilinear) to the input's spatial size, then min-max normalized to `[0, 1]`.
4. A degenerate case — gradients/activations that are perfectly flat or non-finite — produces an all-zero heatmap rather than a `NaN`-filled one or a crash (`_normalize()`); this is a valid (if uninformative) result, not an error.

The target layer is architecture-specific and resolved once, centrally, by `medrisk_ml/models/factory.py::get_target_layer()` — the last convolutional block for `baseline_cnn`, `layer4` for `resnet18` — so nothing downstream hardcodes a layer name.

## What it is not

- **Not a segmentation of tumor tissue.** A "hot" region means "this area's activations were influential for the model's output," not "this is tumor."
- **Not proof that a correct prediction was reached for the right reason**, and equally **not proof that an incorrect prediction was reached for the wrong reason.** A model can be right for a spurious reason (background artifact, scanner-specific texture) and Grad-CAM will faithfully highlight that spurious region — it visualizes the model's actual behavior, including its actual mistakes and shortcuts, not ground truth.
- **Not a substitute for the error analysis in [evaluation.md](evaluation.md).** Grad-CAM is intentionally not invoked anywhere in `medrisk_ml/evaluation/error_analysis.py` — qualitative inspection of one heatmap must never replace the quantitative error breakdown.
- **Not validated against any pathologist annotation in this codebase.** No ground-truth tumor-region mask exists in this pipeline to check Grad-CAM against; any claim of biological correctness would currently be unverifiable.

## Generating overlays

```powershell
python -m medrisk_ml.cli explain --experiment-id <experiment_id> --num-samples 8
```

`cmd_explain` (`medrisk_ml/cli.py`) selects which test-split samples to explain by reading that experiment's `predictions/test_predictions.csv` (written by `evaluate`) and picking, when available, one example of each: true positive, true negative, false positive, false negative, and one "uncertain" sample whose probability is within `0.1` of the frozen threshold — a deliberately mixed sample, not just the model's best-looking cases. If no predictions file exists yet (i.e. `evaluate` hasn't been run), it falls back to the first `--num-samples` test images in dataset order.

Each overlay is rendered by `medrisk_ml/explainability/visualization.py::save_overlay()` — the heatmap is colorized (`jet` colormap) and alpha-blended (`alpha=0.4`) onto the **unnormalized** display image (a separate transform pipeline from the one fed to the model, so the saved PNG shows recognizable colors rather than ImageNet-normalized values) — and saved as `gradcam/<category>_<sample_id>.png`.

## Output

```text
artifacts/experiments/<experiment_id>/gradcam/
├── true_positive_<id>.png
├── true_negative_<id>.png
├── false_positive_<id>.png
├── false_negative_<id>.png
├── uncertain_<id>.png
└── DISCLAIMER.txt
```

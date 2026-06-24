# Dataset card: PatchCamelyon (PCam)

## Summary

PatchCamelyon (PCam) is a binary image-classification benchmark derived from the Camelyon16 challenge dataset of H&E-stained lymph-node histopathology whole-slide images. Each PCam sample is a 96×96 RGB patch extracted from a whole-slide image, labeled:

- **negative (0):** no tumor tissue in the **center 32×32 px region** of the patch.
- **positive (1):** at least one pixel of tumor tissue in that center region.

Tumor tissue *outside* the center region does not make a patch positive — this is a deliberate, narrow labeling rule, not "does this patch contain any cancer anywhere."

## Source and access in this repository

This repository never bundles or commits PCam. `medrisk_ml/data/datasets.py::PCamDataset` wraps `torchvision.datasets.PCAM`, which downloads from its own upstream mirror. Access is gated (see [medrisk_ml/data/download.py](../medrisk_ml/data/download.py)):

1. `medrisk_ml.cli data download --config <cfg>` must be run with the **`--download`** flag, **and**
2. the environment variable **`MEDRISK_ALLOW_DATA_DOWNLOAD=1`** must be set.

Either condition missing is a hard stop with an explanatory message — never a silent fetch. The estimated size of the full distribution is ~7 GB; `check_download_preconditions()` also refuses to proceed unless at least 2× that much free disk space is available.

## Splits

PCam ships fixed train/validation/test splits (`torchvision.datasets.PCAM(split=...)`). This codebase never re-splits or shuffles across them — `medrisk_ml/data/datasets.py::deterministic_subset()` can take a smaller, seeded subset of a split (for fast iteration), but a sample from `test` never leaks into `train`/`val` regardless of subset size.

## Known biases and limitations (read before drawing any conclusion from a PCam-trained model)

- **Single source distribution.** All slides originate from Camelyon16 (Radboud UMC and UMC Utrecht scanners). A model trained here has not seen other scanners, staining protocols, or patient populations — generalization claims beyond this exact data distribution are unsupported.
- **Center-pixel labeling rule.** A patch with extensive tumor tissue everywhere *except* the center 32×32 px is labeled negative. This is a precise, useful benchmark definition, but it is not the same question as "does this patch contain cancer."
- **Patch-level, not slide-level or patient-level.** Many patches come from the same slide/patient. A high patch-level accuracy says nothing about per-patient or per-slide diagnostic performance, and patches from the same slide are correlated, not independent samples.
- **No clinical metadata.** No patient identifiers, demographics, or outcomes are present in PCam, and none are introduced anywhere in this codebase — see the constraint against storing patient-identifying data.
- **Stain/scanner shift is a known, well-documented failure mode** for histopathology models in general; nothing in this phase measures or corrects for it.

## Synthetic substitute dataset

`medrisk_ml/data/synthetic.py::SyntheticHistopathologyDataset` generates deterministic, fully synthetic RGB images (diffuse colored noise; "positive" samples get an extra bright blob injected near the center) — used for fast iteration, unit tests, and CI, where downloading real PCam would be slow, heavy, or simply unwanted. It is visually and statistically nothing like real tissue.

> **SYNTHETIC DATA — NOT MEDICAL PERFORMANCE.** Any metric produced from `SyntheticHistopathologyDataset` (accuracy, ROC-AUC, calibration, anything) reflects only "can the pipeline learn an easy, synthetic, central-blob-detection task." It must never be quoted, plotted, or reported as if it were a measurement of real diagnostic performance. The CLI and test suite print/assert this distinction explicitly wherever synthetic data is used (`medrisk_ml.constants.SYNTHETIC_DATA_WARNING`).

## Class balance

PCam's official splits are close to class-balanced by construction (~50/50 negative/positive in `train`). `medrisk_ml/data/metadata.py::inspect_split()` computes and reports the actual per-split class distribution for whatever dataset is configured — never assume balance without checking the generated `artifacts/dataset_reports/.../dataset_report.json` for the run in question.

## Intended use in this project

PCam (real) is intended **only** for the optional, non-automatic ResNet18 transfer-learning experiments described in [experiment-protocol.md](experiment-protocol.md) — research/educational use, never a clinical claim. See the top-level medical disclaimer repeated in every report and model card this pipeline produces.

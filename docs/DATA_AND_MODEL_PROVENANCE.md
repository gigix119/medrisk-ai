# Data and model provenance

A single page answering "where did this data/model actually come from, and what am I allowed
to do with it?" — consolidating facts already documented separately in
[dataset-card-pcam.md](dataset-card-pcam.md), the registered model's `model_card.md`, and
`research/references.yaml`, for anyone (recruiter, future contributor) who wants the
provenance answer without reading every phase's docs.

## Public demo dataset

**Name:** Synthetic Histopathology Demonstration Dataset
**Source:** Generated locally by `medrisk_ml.data.synthetic.SyntheticHistopathologyDataset`
(deterministic, seed `42`) — not downloaded from anywhere, not derived from any real
patient or public dataset.
**Version registered in the web dataset registry:** `synthetic-histopathology-demo` v`1.0.0`
(50 samples: 30 train / 10 val / 10 test), seeded by `scripts/seed_dataset.py`.
**License/redistribution:** N/A — this is procedurally generated noise plus an injected
bright blob for the "positive" class, not third-party content. No attribution is owed to
anyone because no one else's data was used.
**What it looks like:** diffuse colored noise; visually and statistically nothing like real
tissue. See [dataset-card-pcam.md](dataset-card-pcam.md) "Synthetic substitute dataset" for
the exact generation logic.
**Public display:** Fully permitted — every sample is server-generated, contains no PII, no
EXIF/embedded metadata (it never existed as a photographed image), and no licensing
restriction. Every UI surface that shows it labels it `is_synthetic=true`/"Synthetic
Histopathology Demonstration Dataset" explicitly — never presented as real tissue.
**Ground truth:** The "label" is the generator's own deterministic rule, not an expert
annotation — there is no pathologist behind these labels because there is no tissue.

## Real dataset referenced (but never bundled or auto-downloaded)

**Name:** PatchCamelyon (PCam) — see [dataset-card-pcam.md](dataset-card-pcam.md) for the
full card (labeling rule, known biases, source distribution).
**Source:** Derived from Camelyon16 (Radboud UMC / UMC Utrecht), accessed in this codebase
only via `torchvision.datasets.PCAM`, which fetches from its own upstream mirror.
**Citation:** Veeling, B.S., Linmans, J., Winkens, J., Cohen, T. and Welling, M. (2018).
*Rotation Equivariant CNNs for Digital Pathology.* MICCAI 2018. DOI
`10.1007/978-3-030-00934-2_24` (verified against the Springer chapter page, the official
`basveeling/pcam` GitHub repo, and arXiv:1806.03962 — see `research/references.yaml`).
**Redistribution status:** This repository **never commits, bundles, or auto-downloads**
PCam. Access requires both an explicit CLI flag and `MEDRISK_ALLOW_DATA_DOWNLOAD=1` (see
[dataset-card-pcam.md](dataset-card-pcam.md) "Source and access"). No PCam sample has ever
been used in the public demo, the registered model, or any evaluation artifact currently in
this repository — the gate exists for a *future* real-model experiment, not anything shipped
today.
**Public demo eligibility:** None currently. If a real PCam-trained model is ever added,
revisit this section before showing any PCam-derived sample publicly — PCam's own license
terms (inherited from Camelyon16) would need to be re-checked at that time, not assumed
unchanged from this writing.

## Registered model artifact

**Model ID:** `smoke-baseline-cnn:0.0.1-smoke` — the **only** model bundle that exists in
this repository (`artifacts/model_registry/smoke-baseline-cnn/0.0.1-smoke/`).
**Architecture:** `baseline_cnn`, trained on `SyntheticHistopathologyDataset` (see above) —
`dataset_name: "synthetic"`, `dataset_mode: "synthetic"` in the bundle's own
`manifest.json`.
**`synthetic_only: true`, `eligible_for_demo: false`** — both fields read directly from
`manifest.json`, enforced structurally (`load_bundle()` refuses a bundle where both
`synthetic_only` and `eligible_for_demo` are true; production deployment refuses to start
with a synthetic bundle at all — see [model-deployment.md](model-deployment.md) and
[THREAT_MODEL.md](THREAT_MODEL.md) threat #10).
**Validation/test metrics in the manifest** (accuracy 1.0, ROC-AUC 1.0, etc.) reflect a
trivially easy synthetic classification task (detecting an injected bright blob), **not**
real diagnostic performance. Quoting these numbers as if they measured anything clinical
would misrepresent them — see the dataset card's explicit warning,
`medrisk_ml.constants.SYNTHETIC_DATA_WARNING`, and every model/evaluation surface in the
frontend that labels this explicitly.
**Integrity verification:** `SHA256SUMS` file in the bundle directory, checked at every load
(`medrisk_ml.registry.bundle.verify_bundle`), not just at registration time. The model state
dict is loaded with `torch.load(..., weights_only=True)` (`medrisk_inference/runtime.py:107`)
— see [SECURITY_AUDIT.md](SECURITY_AUDIT.md) finding F-4 for why the pinned torch version
matters here.
**Hash policy:** Any bundle whose `SHA256SUMS`-verified checksum fails is rejected at load
time with `BundleInvalidError` — there is no "load anyway" override.

## Known provenance gaps

- No real (non-synthetic) trained model exists in this repository — this is the actual
  release blocker documented in [DEPLOYMENT.md](DEPLOYMENT.md), not a missing deployment
  step.
- `research/references.yaml` currently has 4 verified entries (Grad-CAM, PCam, scikit-learn,
  PyTorch). It does not yet cover every method/library used in this codebase (e.g. FastAPI,
  SQLAlchemy, Argon2/pwdlib are not in the structured citation registry) — those are
  documented informally in `docs/decisions/ADR-001-backend-architecture.md` instead.
- No independent re-verification of the four `references.yaml` entries was performed this
  session (they were verified in the Phase 7 session, per that file's own
  `verification_note` fields, against live sources on 2026-06-25) — treat that date as the
  last-checked date, not "checked today."

"""Phase 7 research platform: scientific evaluation, reproducibility, leakage detection,
model comparison and error analysis on top of the Phase 6 dataset registry.

This package is deliberately light - no numpy/torch/sklearn - so the live API process can
import it freely. Heavy numeric evaluation work (metrics, bootstrap CI, calibration) happens
offline in `medrisk_ml.evaluation` and is bridged into Postgres by the separate
`medrisk_research` CLI package; this package only ever reads back what that CLI already
persisted. See docs/PHASE_7_PROGRESS.md for the full architecture rationale.
"""

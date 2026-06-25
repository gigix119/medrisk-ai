"""Offline research-evaluation CLI bridge (Phase 7).

Sibling package to `medrisk_ml`/`medrisk_inference`. Today's commands (`validate-study`,
`load-study`, `quality-audit`, `leakage-audit`, `ingest-evaluation`) only need Postgres
(`app.db`/`app.models`) + PyYAML + the standard library - they read already-computed
artifact files (a completed `medrisk_ml` experiment's `metrics.json`/`environment.json`/
predictions CSV) rather than running fresh inference or recomputing metrics, so no
numpy/torch/sklearn import is needed here. That keeps this package testable against the same
Postgres test database as `tests/integration/` (PyYAML is installed via
`requirements-dev.txt`, never `requirements.txt` - the live API still never imports this
package or `yaml` at all, so its dependency footprint is untouched).

A *future* `evaluate` command that runs a fresh model pass and recomputes metrics via
`medrisk_ml.evaluation.*` would need the full `requirements-ml.txt` stack as well - see
docs/PHASE_7_PROGRESS.md "Remaining tasks" for why that isn't implemented yet, and the open
question it would raise (no current CI job has both Postgres and the ml dependency stack).

Run as `python -m medrisk_research.cli <subcommand>`, mirroring `medrisk_ml/cli.py`'s
single-file-with-subcommands convention.
"""

# Research methodology

This document specifies the experimental protocol this repository's research platform
*supports* — the rules a study, dataset, and evaluation run must follow to be persisted at
all. It is deliberately separate from
[PORTFOLIO_CASE_STUDY.md](PORTFOLIO_CASE_STUDY.md), which describes what has actually been
*executed* with this protocol (currently: one synthetic demonstration study, nothing claiming
real diagnostic performance). Read this document to understand the protocol; read the case
study to understand what has been run through it so far.

## Research objective

To evaluate, in a leakage-controlled and fully reproducible way, whether a binary histopathology
patch classifier (tumor tissue present/absent in a patch's center region, the PCam task
formulation) achieves a given level of discriminative and calibration performance on a held-out
test split, and to make every number behind that claim traceable back to a configuration, a
model artifact, and a set of individual sample predictions.

## Research questions / hypothesis framing

A study (`research/studies/*.yaml`, validated against `app.research.schemas.study.StudyConfig`)
must state an explicit `research_question` and `hypothesis` field. The repository's one existing
study is explicit that it tests engineering correctness, not a clinical hypothesis: *"No
clinical hypothesis is being tested. The only claim under test is engineering correctness of the
pipeline itself."* Any future study using real data should state a real discriminative or
calibration hypothesis (e.g. "ROC-AUC on the test split exceeds 0.90") rather than leaving this
field as a placeholder.

## Dataset assumptions

A dataset entering this protocol must declare, in its `StudyConfig.dataset` section: a
provenance classification (synthetic / real-licensed / real-unlicensed, etc.), a task type, the
full set of target classes and which one is positive, inclusion/exclusion rules, a split
strategy, and a random seed. The dataset registry (`Dataset`/`DatasetSample` tables, Phase 6)
enforces a subset of this structurally — every sample row has a non-null `ground_truth_label`,
`split`, and `checksum_sha256` — and the quality audit (below) checks the rest empirically.

## Sample unit

The unit of evaluation is one image patch (currently 96×96, 3-channel), corresponding to PCam's
patch-level task definition. This protocol does not currently support slide-level or
patient-level aggregation; a result computed under this protocol is a patch-level result and must
not be reported as a patient- or slide-level diagnostic rate without an explicit, separately
documented aggregation step (none exists in this repository).

## Label handling

Ground truth is a single categorical label per sample (`negative`/`positive` for the binary
task), stored once on `DatasetSample.ground_truth_label` and never re-derived or overridden by
the evaluation pipeline. For the synthetic dataset, the label is the generator's own
deterministic rule (presence of an injected bright region), not an expert annotation — there is
no pathologist behind these labels because there is no tissue. A future real-data study must
document its annotation process in the dataset's `inclusion_rules`/`exclusion_rules` fields
rather than assuming this protocol can validate label quality on its own.

## Split strategy

`StudyConfig.dataset.split_strategy` is currently `predefined` — splits are assigned once, at
dataset-generation or dataset-import time, and never re-shuffled by the evaluation pipeline.
`train_split`, `validation_split`, and `test_split` are named explicitly rather than assumed to
be `train`/`val`/`test` strings, though that is the convention used today.

## Evaluation protocol

One `EvaluationRun` is one model version, evaluated on one dataset version's one split, exactly
once. A `status=completed` run is treated as immutable everywhere in this codebase —
re-evaluating the same model/dataset/split combination creates a new row rather than mutating
the old one, so a historical result can never silently change. The protocol enforces a strict
ordering: any decision threshold (`threshold_strategy`, e.g. `max_f1`) and any calibration
(`calibration_enabled` + `calibration_fit_split`) must be selected on the validation split
*before* the test split is evaluated, and the test split is then evaluated exactly once with
those frozen values. This is enforced twice, independently:

- `medrisk_ml.evaluation.thresholding.select_threshold` raises `SplitLeakageError` if asked to
  fit against `split_name="test"`.
- `app.research.domain.policy.reject_test_split_fitting` raises `SplitProtocolViolationError`
  for the same case at the research-platform/config level, and `StudyConfig`'s evaluation schema
  types `threshold_fit_split`/`calibration_fit_split` so that `test` is not even an accepted
  value at config-validation time.

## Metric selection

`StudyConfig.evaluation.primary_metric` names one metric (e.g. `roc_auc`) as the headline number
for a study; `secondary_metrics` lists the rest to report alongside it (e.g. `pr_auc`,
`sensitivity`, `specificity`, `f1`, `accuracy`, `brier_score`). See
[PORTFOLIO_CASE_STUDY.md "Implemented metrics"](PORTFOLIO_CASE_STUDY.md#10-implemented-metrics)
for the full definition table. ROC-AUC/PR-AUC are preferred as primary metrics because they are
threshold-independent; accuracy alone is intentionally never the only metric a study can declare,
because it is misleading under class imbalance.

## Class imbalance considerations

The dataset quality audit computes a class imbalance ratio
(`max(per-class count) / min(per-class count)`) and flags anything above 3:1 as a warning
finding. A study evaluating an imbalanced dataset should declare balanced accuracy and/or PR-AUC
as at least a secondary metric, since plain accuracy on an imbalanced split rewards a model that
ignores the minority class. `StudyConfig.training.class_weighting` exists as a configuration
field for a future training run that needs to compensate for imbalance during fitting, not just
report it.

## Decision thresholds

The inference-serving path (`medrisk_inference`) applies a decision pipeline: raw probability →
calibration (temperature scaling, fit on validation only) → a fixed decision threshold → a
review-policy band that can produce a `review_required` verdict instead of a forced binary
choice when the calibrated probability falls inside an uncertain range around the threshold. This
three-way verdict (`negative`/`positive`/`review_required`) is a deliberate design choice: a
binary forced choice near the decision boundary is exactly where a model is least trustworthy.

## Sample-level error analysis

Every evaluated sample is persisted as one `EvaluationSamplePrediction` row (ground truth,
predicted class, full probability vector, confidence, correctness, optional `error_type`). This
is what backs `GET /research/evaluations/{id}/errors`, filterable by correctness, and the
offline `error_analysis.csv`/`.md` artifacts produced by `medrisk_ml`. The protocol requires this
level of granularity specifically so a false-negative-heavy result, for example, can be
investigated at the level of which individual samples were missed, rather than stopping at an
aggregate recall number.

## Explainability protocol

Grad-CAM is computed only as a post-hoc explanation of an already-finalized prediction; it never
participates in training, calibration, threshold selection, or the reported metrics. Every
Grad-CAM output (offline or live) is required to carry a disclaimer that it identifies regions
associated with the class score and does not establish causal reasoning or clinical validity.
The protocol does not currently define a quantitative explainability evaluation (e.g. deletion
metrics, sanity checks against a randomized model) — this is a documented gap, not an implied
guarantee that the heatmaps are validated as faithful.

## Leakage prevention

Beyond the threshold/calibration split discipline above, the dataset leakage audit
(`app/research/services/leakage_audit_service.py`) checks for exact cross-split overlap by file
checksum or on-disk path, conflicting labels on identical content, and group-level (subject/
patient/slide) overlap when a recognized grouping identifier is present in sample metadata. When
no such identifier exists — true of the current synthetic dataset — the audit reports
"could not be evaluated" rather than a false "no leakage found." Near-duplicate detection via
perceptual hashing is explicitly out of scope today; see
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## Dataset quality checks

The quality audit (`app/research/services/dataset_quality_service.py`) is a precondition for
trusting any metric computed from a dataset: per-split and per-class counts, declared-vs-actual
class labels, image dimension/format consistency, duplicate-checksum and path-collision
detection, and a full filesystem cross-check (every registered sample's file must exist and
match its registered checksum). A dataset with `FAILED` quality-audit status should not be used
as the basis for a study whose results are intended to be cited.

## Reproducibility requirements

A study config is hashed (`config_hash`) and that hash, together with the resolved configuration
and an artifact manifest, is persisted on the `EvaluationRun` row. A trained model's manifest
records its git commit, dataset name/version/mode, and seed. Together, these mean a reported
metric can always be traced to: the exact study configuration, the exact model artifact
(checksum-verified), and the exact dataset version it was computed against — the prerequisite for
any external party re-running the same protocol and expecting the same result.

## Ethical considerations

No real patient data, human subjects, or biological material has been used anywhere in this
repository's current artifacts — the one dataset is procedurally generated. Should a real,
licensed dataset (e.g. PCam) ever be substituted in, this section must be revisited: PCam's own
license terms (inherited from Camelyon16) would need to be reconfirmed before any sample is shown
publicly, and any institutional/ethical approval requirements for the underlying data would need
to be checked independently of this repository's own protocol — neither is something this
codebase can verify on its own.

## Clinical safety boundary

This protocol produces research measurements, not clinical validations. `ScientificMaturity`
labels (e.g. `synthetic_demo`) are attached to every result and are structurally prevented from
being upgraded to a clinical-sounding claim: `assert_not_forbidden_label` raises rather than
rendering banned phrases such as "clinically validated" or "safe for diagnosis" anywhere
generated text is produced. See
[PORTFOLIO_CASE_STUDY.md "Scope and clinical safety boundary"](PORTFOLIO_CASE_STUDY.md#4-scope-and-clinical-safety-boundary).

## Interpretation limits

A patch-level metric computed under this protocol — even on real data — does not by itself imply
slide-level or patient-level diagnostic performance, because patches drawn from the same slide
are correlated rather than independent samples. A high ROC-AUC under this protocol demonstrates
that the model separates the two classes well on the evaluated patch population; it is not, on
its own, evidence of generalization to a different hospital's scanner, staining protocol, or
patient population.

## Requirements for future external validation

Before any result produced under this protocol could support an external or clinical claim, it
would need: real, licensed data with documented provenance (not the synthetic generator);
external validation on data from a source distribution disjoint from training (a different
scanner/hospital, at minimum); a pre-registered primary metric and hypothesis (not selected after
seeing results); comparison against a published benchmark using an equivalent protocol; and a
formal review process outside this repository's own self-administered checks. None of these steps
has been attempted here — this protocol is built to support them, not to claim they have already
happened.

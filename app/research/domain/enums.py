"""Scientific-integrity classification enums for the research platform (Phase 7).

These enums are deliberately closed sets: a model or evaluation result can never carry a
label outside them - there is structurally no way to write "clinically validated",
"medically approved" or "doctor-level accuracy" into any of these columns. See
`app.research.domain.policy` for the disclaimer text and validation helpers that sit
alongside these, and docs/PHASE_7_PROGRESS.md ("Architecture decisions", item 5) for why
this lives in its own module rather than scattered across services.
"""

from __future__ import annotations

import enum


class ResultClassification(str, enum.Enum):
    """How an evaluation run's numbers may be interpreted - never inferred from context,
    always set explicitly when the run is created."""

    SYNTHETIC_DEMO = "synthetic_demo"
    EXPLORATORY_VALIDATION = "exploratory_validation"
    CROSS_VALIDATION = "cross_validation"
    HELD_OUT_TEST = "held_out_test"
    EXTERNAL_TEST = "external_test"
    BENCHMARK = "benchmark"
    UNKNOWN = "unknown"


class ScientificMaturity(str, enum.Enum):
    """Where a model sits on the path from "proves the pipeline runs" to "a real research
    candidate" - distinct from `ResultClassification`, which describes one evaluation run
    rather than the model as a whole."""

    SYNTHETIC_DEMO = "synthetic_demo"
    PROTOTYPE = "prototype"
    EXPERIMENTAL = "experimental"
    BENCHMARK_CANDIDATE = "benchmark_candidate"
    SELECTED_RESEARCH_MODEL = "selected_research_model"
    ARCHIVED = "archived"
    UNKNOWN = "unknown"


class DatasetProvenanceType(str, enum.Enum):
    """Classification of where a dataset's samples actually came from. Never inferred from a
    filename - set explicitly at registration time, defaulting to PROVENANCE_UNKNOWN."""

    SYNTHETIC = "synthetic"
    TEST_FIXTURE = "test_fixture"
    PUBLIC_UNRESTRICTED = "public_unrestricted"
    PUBLIC_LICENSE_RESTRICTED = "public_license_restricted"
    LOCALLY_PROVIDED = "locally_provided"
    UNAVAILABLE = "unavailable"
    PROVENANCE_UNKNOWN = "provenance_unknown"


class AuditStatus(str, enum.Enum):
    """Outcome of a dataset quality or leakage audit."""

    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"
    UNKNOWN = "unknown"
    INCOMPLETE = "incomplete"


class Severity(str, enum.Enum):
    """Severity of one finding inside a quality/leakage audit summary."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RunStatus(str, enum.Enum):
    """Lifecycle of an experiment run or evaluation run. A run's metrics/predictions must
    only ever be trusted when status == COMPLETED - PENDING/RUNNING rows have no results
    yet, and FAILED/CANCELLED/INVALIDATED rows must never be presented as complete."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INVALIDATED = "invalidated"


class StudyStatus(str, enum.Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    RUNNING = "running"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class MetricStatus(str, enum.Enum):
    """Whether a single reported metric value is trustworthy - mirrors the master spec's
    `{"name": ..., "value": null, "status": "undefined", "reason": ...}` shape so a NaN from
    `medrisk_ml.evaluation.metrics` is never silently rendered as 0.0."""

    OK = "ok"
    UNDEFINED = "undefined"
    UNAVAILABLE = "unavailable"

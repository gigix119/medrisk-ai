"""Integration tests for evaluation-run endpoints (Phase 7).

Builds an `EvaluationRun` + `EvaluationSamplePrediction` rows directly via the repository
layer (mirroring what `medrisk_research.cli ingest-evaluation` does in production), then
exercises every read endpoint plus the `POST .../evaluations` pending-row creation path -
no metric is ever computed by these tests; everything is asserted against numbers the test
itself wrote into the database, exactly like the real ingestion CLI would.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation import EvaluationSamplePrediction
from app.research.domain.enums import ResultClassification
from app.research.domain.metric_shaping import extract_counts, shape_scalar_metrics
from app.research.repositories import evaluation as evaluation_repo
from tests.integration.conftest import AuthTokens, SeededDataset


async def _create_completed_evaluation(
    db_session: AsyncSession,
    *,
    dataset_id: uuid.UUID,
    negative_sample_id: uuid.UUID,
    positive_sample_id: uuid.UUID,
) -> uuid.UUID:
    run = await evaluation_repo.create_pending_evaluation_run(
        db_session,
        dataset_id=dataset_id,
        model_id="smoke-baseline-cnn",
        model_version="0.0.1-smoke",
        split_name="test",
        result_classification=ResultClassification.SYNTHETIC_DEMO,
    )

    raw_test_metrics = {
        "accuracy": 0.5,
        "balanced_accuracy": 0.5,
        "precision": 1.0,
        "recall": 0.0,
        "sensitivity": 0.0,
        "specificity": 1.0,
        "f1": float("nan"),
        "roc_auc": float("nan"),
        "pr_auc": float("nan"),
        "brier_score": 0.25,
        "true_positive": 0,
        "true_negative": 1,
        "false_positive": 0,
        "false_negative": 1,
        "sample_count": 2,
        "positive_count": 1,
        "negative_count": 1,
    }
    metrics_payload = {
        "class_names": ["negative", "positive"],
        "positive_class": "positive",
        "scalar_metrics": shape_scalar_metrics(raw_test_metrics),
        "counts": extract_counts(raw_test_metrics),
    }

    await evaluation_repo.bulk_create_sample_predictions(
        db_session,
        [
            EvaluationSamplePrediction(
                evaluation_run_id=run.id,
                dataset_sample_id=negative_sample_id,
                sample_key="negative-001",
                split="train",
                ground_truth_label="negative",
                predicted_class="negative",
                probabilities={"negative": 0.9, "positive": 0.1},
                confidence=0.9,
                is_correct=True,
                error_type=None,
                inference_duration_ms=12.5,
                metadata_json=None,
            ),
            EvaluationSamplePrediction(
                evaluation_run_id=run.id,
                dataset_sample_id=positive_sample_id,
                sample_key="positive-001",
                split="train",
                ground_truth_label="positive",
                predicted_class="negative",
                probabilities={"negative": 0.6, "positive": 0.4},
                confidence=0.6,
                is_correct=False,
                error_type="false_negative",
                inference_duration_ms=11.0,
                metadata_json=None,
            ),
        ],
    )

    await evaluation_repo.mark_evaluation_run_completed(
        db_session,
        run,
        completed_at=datetime.now(UTC),
        primary_metric_name="roc_auc",
        primary_metric_value=None,
        metrics=metrics_payload,
        confidence_intervals=None,
        calibration_metrics=None,
        threshold_metrics=None,
        artifact_manifest={"schema_version": "1.0", "file_sha256": {}},
        protocol_hash="testhash",
        notes="Test fixture evaluation run.",
    )
    await db_session.commit()
    return run.id


async def test_list_evaluations_includes_created_run(
    client: AsyncClient,
    auth_tokens: AuthTokens,
    db_session: AsyncSession,
    seeded_dataset: SeededDataset,
) -> None:
    evaluation_id = await _create_completed_evaluation(
        db_session,
        dataset_id=seeded_dataset.dataset_id,
        negative_sample_id=seeded_dataset.negative_sample_id,
        positive_sample_id=seeded_dataset.positive_sample_id,
    )
    response = await client.get(
        "/api/v1/research/evaluations",
        params={"dataset_id": str(seeded_dataset.dataset_id)},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert str(evaluation_id) in ids


async def test_get_evaluation_detail(
    client: AsyncClient,
    auth_tokens: AuthTokens,
    db_session: AsyncSession,
    seeded_dataset: SeededDataset,
) -> None:
    evaluation_id = await _create_completed_evaluation(
        db_session,
        dataset_id=seeded_dataset.dataset_id,
        negative_sample_id=seeded_dataset.negative_sample_id,
        positive_sample_id=seeded_dataset.positive_sample_id,
    )
    response = await client.get(
        f"/api/v1/research/evaluations/{evaluation_id}", headers=auth_tokens.auth_header
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["result_classification"] == "synthetic_demo"
    assert body["notes"] == "Test fixture evaluation run."


async def test_get_evaluation_metrics_shapes_undefined_values(
    client: AsyncClient,
    auth_tokens: AuthTokens,
    db_session: AsyncSession,
    seeded_dataset: SeededDataset,
) -> None:
    evaluation_id = await _create_completed_evaluation(
        db_session,
        dataset_id=seeded_dataset.dataset_id,
        negative_sample_id=seeded_dataset.negative_sample_id,
        positive_sample_id=seeded_dataset.positive_sample_id,
    )
    response = await client.get(
        f"/api/v1/research/evaluations/{evaluation_id}/metrics", headers=auth_tokens.auth_header
    )
    assert response.status_code == 200
    body = response.json()
    by_name = {m["name"]: m for m in body["scalar_metrics"]}
    assert by_name["roc_auc"]["status"] == "undefined"
    assert by_name["roc_auc"]["value"] is None
    assert by_name["roc_auc"]["reason"] is not None
    assert by_name["accuracy"]["status"] == "ok"
    assert by_name["accuracy"]["value"] == 0.5
    assert body["counts"]["true_negative"] == 1


async def test_confusion_matrix_reflects_stored_counts(
    client: AsyncClient,
    auth_tokens: AuthTokens,
    db_session: AsyncSession,
    seeded_dataset: SeededDataset,
) -> None:
    evaluation_id = await _create_completed_evaluation(
        db_session,
        dataset_id=seeded_dataset.dataset_id,
        negative_sample_id=seeded_dataset.negative_sample_id,
        positive_sample_id=seeded_dataset.positive_sample_id,
    )
    response = await client.get(
        f"/api/v1/research/evaluations/{evaluation_id}/confusion-matrix",
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["matrix"] == [[1, 0], [1, 0]]  # [[TN, FP], [FN, TP]]


async def test_confusion_matrix_unavailable_for_pending_run(
    client: AsyncClient, superuser_auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    create_response = await client.post(
        "/api/v1/research/evaluations",
        headers=superuser_auth_tokens.auth_header,
        json={
            "dataset_id": str(seeded_dataset.dataset_id),
            "model_id": "smoke-baseline-cnn",
            "model_version": "0.0.1-smoke",
            "split_name": "test",
            "result_classification": "synthetic_demo",
        },
    )
    evaluation_id = create_response.json()["id"]
    response = await client.get(
        f"/api/v1/research/evaluations/{evaluation_id}/confusion-matrix",
        headers=superuser_auth_tokens.auth_header,
    )
    body = response.json()
    assert body["available"] is False
    assert body["reason"] is not None


async def test_list_errors_filters_by_is_correct(
    client: AsyncClient,
    auth_tokens: AuthTokens,
    db_session: AsyncSession,
    seeded_dataset: SeededDataset,
) -> None:
    evaluation_id = await _create_completed_evaluation(
        db_session,
        dataset_id=seeded_dataset.dataset_id,
        negative_sample_id=seeded_dataset.negative_sample_id,
        positive_sample_id=seeded_dataset.positive_sample_id,
    )
    response = await client.get(
        f"/api/v1/research/evaluations/{evaluation_id}/errors",
        params={"is_correct": "false"},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["error_type"] == "false_negative"
    assert body["items"][0]["ground_truth_label"] == "positive"


async def test_create_pending_evaluation_with_unknown_dataset_returns_404(
    client: AsyncClient, superuser_auth_tokens: AuthTokens
) -> None:
    response = await client.post(
        "/api/v1/research/evaluations",
        headers=superuser_auth_tokens.auth_header,
        json={
            "dataset_id": str(uuid.uuid4()),
            "model_id": "smoke-baseline-cnn",
            "model_version": "0.0.1-smoke",
            "split_name": "test",
            "result_classification": "synthetic_demo",
        },
    )
    assert response.status_code == 404


async def test_get_unknown_evaluation_returns_404(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    response = await client.get(
        f"/api/v1/research/evaluations/{uuid.uuid4()}", headers=auth_tokens.auth_header
    )
    assert response.status_code == 404

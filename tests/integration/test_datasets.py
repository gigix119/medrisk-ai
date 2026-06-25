"""Integration tests for the dataset registry + controlled sample inference (Phase 6).

The session-wide test model (see tests/conftest.py) is a deterministic, constant-output
32x32 synthetic model whose calibrated probability is always exactly 0.5, landing every
request in `review_required` with `threshold=0.5`. What matters for these tests is dataset
plumbing (lookup, 404s, ground-truth comparison, history filters) - exhaustive
positive/negative decision-boundary coverage already lives in tests/inference/test_decision.py.
"""

from __future__ import annotations

import io
import uuid

import numpy as np
from httpx import AsyncClient
from PIL import Image

from tests.integration.conftest import AuthTokens, SeededDataset


async def test_list_datasets_includes_seeded_dataset(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    response = await client.get("/api/v1/datasets", headers=auth_tokens.auth_header)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert str(seeded_dataset.dataset_id) in ids


async def test_dataset_detail_returns_metadata(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    response = await client.get(
        f"/api/v1/datasets/{seeded_dataset.dataset_id}", headers=auth_tokens.auth_header
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_synthetic"] is True
    assert body["classes"] == ["negative", "positive"]
    assert "intended_use" in body and "prohibited_use" in body


async def test_invalid_dataset_id_returns_404(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    response = await client.get(f"/api/v1/datasets/{uuid.uuid4()}", headers=auth_tokens.auth_header)
    assert response.status_code == 404


async def test_list_samples_filters_by_class_index(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    response = await client.get(
        f"/api/v1/datasets/{seeded_dataset.dataset_id}/samples",
        params={"class_index": 1},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == str(seeded_dataset.positive_sample_id)
    assert items[0]["ground_truth_label"] == "positive"
    assert "relative_path" not in items[0]


async def test_list_samples_filters_by_split(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    response = await client.get(
        f"/api/v1/datasets/{seeded_dataset.dataset_id}/samples",
        params={"split": "train"},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 200
    assert response.json()["total"] == 2


async def test_invalid_sample_id_returns_404(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    response = await client.get(
        f"/api/v1/datasets/{seeded_dataset.dataset_id}/samples/{uuid.uuid4()}",
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 404


async def test_sample_from_other_dataset_returns_404(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    """A sample id that exists, but under a different (nonexistent) dataset id, must 404 -
    never fall through to returning the sample anyway."""
    response = await client.get(
        f"/api/v1/datasets/{uuid.uuid4()}/samples/{seeded_dataset.positive_sample_id}",
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 404


async def test_sample_image_endpoint_returns_png_bytes(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    response = await client.get(
        f"/api/v1/datasets/{seeded_dataset.dataset_id}"
        f"/samples/{seeded_dataset.positive_sample_id}/image",
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"


async def test_predict_on_known_sample_returns_ground_truth_and_correctness(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    response = await client.post(
        f"/api/v1/datasets/{seeded_dataset.dataset_id}"
        f"/samples/{seeded_dataset.positive_sample_id}/predict",
        json={"include_explanation": False},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["dataset_id"] == str(seeded_dataset.dataset_id)
    assert body["dataset_sample_id"] == str(seeded_dataset.positive_sample_id)
    assert body["ground_truth_label"] == "positive"
    assert body["is_correct"] == (body["predicted_class"] == "positive")
    assert body["explanation"]["status"] == "not_requested"
    assert "research_disclaimer" in body
    assert any("synthetic" in warning.lower() for warning in body["warnings"])


async def test_predict_with_explanation_returns_gradcam(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    response = await client.post(
        f"/api/v1/datasets/{seeded_dataset.dataset_id}"
        f"/samples/{seeded_dataset.negative_sample_id}/predict",
        json={"include_explanation": True},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 201
    assert response.json()["explanation"]["status"] == "available"


async def test_predict_invalid_sample_returns_404(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    response = await client.post(
        f"/api/v1/datasets/{seeded_dataset.dataset_id}/samples/{uuid.uuid4()}/predict",
        json={},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 404


async def test_prediction_on_sample_appears_in_history_with_provenance(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    predict_response = await client.post(
        f"/api/v1/datasets/{seeded_dataset.dataset_id}"
        f"/samples/{seeded_dataset.positive_sample_id}/predict",
        json={},
        headers=auth_tokens.auth_header,
    )
    prediction_id = predict_response.json()["prediction_id"]

    history_response = await client.get(
        "/api/v1/predictions/history", headers=auth_tokens.auth_header
    )
    items = history_response.json()["items"]
    assert len(items) == 1
    item = items[0]
    assert item["id"] == prediction_id
    assert item["dataset_id"] == str(seeded_dataset.dataset_id)
    assert item["dataset_sample_id"] == str(seeded_dataset.positive_sample_id)
    assert item["split"] == "train"
    assert item["ground_truth_label"] == "positive"
    assert item["is_correct"] is not None


async def test_legacy_upload_prediction_has_no_ground_truth(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    """Predictions created via the (still-functional, no-longer-publicly-surfaced) arbitrary
    upload endpoint must never gain a fabricated dataset/ground-truth identity."""
    pixels = np.zeros((32, 32, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buffer, format="PNG")

    await client.post(
        "/api/v1/predictions/histopathology",
        files={"file": ("patch.png", buffer.getvalue(), "image/png")},
        headers=auth_tokens.auth_header,
    )

    history_response = await client.get(
        "/api/v1/predictions/history", headers=auth_tokens.auth_header
    )
    item = history_response.json()["items"][0]
    assert item["dataset_id"] is None
    assert item["dataset_sample_id"] is None
    assert item["split"] is None
    assert item["ground_truth_label"] is None
    assert item["is_correct"] is None


async def test_history_filter_by_dataset_id(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    await client.post(
        f"/api/v1/datasets/{seeded_dataset.dataset_id}"
        f"/samples/{seeded_dataset.positive_sample_id}/predict",
        json={},
        headers=auth_tokens.auth_header,
    )

    response = await client.get(
        "/api/v1/predictions/history",
        params={"dataset_id": str(seeded_dataset.dataset_id)},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1

    other_response = await client.get(
        "/api/v1/predictions/history",
        params={"dataset_id": str(uuid.uuid4())},
        headers=auth_tokens.auth_header,
    )
    assert other_response.json()["total"] == 0


async def test_history_filter_by_is_correct(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    predict_response = await client.post(
        f"/api/v1/datasets/{seeded_dataset.dataset_id}"
        f"/samples/{seeded_dataset.positive_sample_id}/predict",
        json={},
        headers=auth_tokens.auth_header,
    )
    is_correct = predict_response.json()["is_correct"]

    matching = await client.get(
        "/api/v1/predictions/history",
        params={"is_correct": str(is_correct).lower()},
        headers=auth_tokens.auth_header,
    )
    assert matching.json()["total"] == 1

    opposite = await client.get(
        "/api/v1/predictions/history",
        params={"is_correct": str(not is_correct).lower()},
        headers=auth_tokens.auth_header,
    )
    assert opposite.json()["total"] == 0

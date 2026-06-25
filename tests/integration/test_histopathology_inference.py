"""Integration tests for the real histopathology inference endpoint (Phase 3).

The session-wide test bundle (see tests/conftest.py) is a deterministic, constant-output
32x32 synthetic model whose review_policy brackets its fixed 0.5 output - every successful
request below lands on `review_required`. Exhaustive negative/positive decision-boundary
coverage lives in tests/inference/test_decision.py; this file is about the HTTP wiring:
auth, persistence, status codes, and what is/isn't ever returned to the client.
"""

from __future__ import annotations

import io
import uuid

import numpy as np
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.prediction import Prediction
from tests.integration.conftest import AuthTokens

ENDPOINT = "/api/v1/predictions/histopathology"


def _png_bytes(size: int = 32, seed: int = 0) -> bytes:
    pixels = np.random.default_rng(seed).integers(0, 256, size=(size, size, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


async def _count_predictions(session: AsyncSession) -> int:
    result = await session.execute(select(Prediction))
    return len(result.scalars().all())


async def test_successful_inference_returns_201_review_required(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    response = await client.post(
        ENDPOINT,
        files={"file": ("patch.png", _png_bytes(), "image/png")},
        headers=auth_tokens.auth_header,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "review_required"
    assert body["decision"] == "review_required"
    assert body["calibrated_probability"] == 0.5
    assert body["review_policy"] == {
        "negative_probability_max": 0.3,
        "positive_probability_min": 0.7,
    }
    assert body["model"]["synthetic_only"] is True
    assert body["input"]["original_width"] == 32
    assert body["input"]["original_height"] == 32
    assert body["timings"]["total_ms"] >= 0.0
    assert body["explanation"]["status"] == "not_requested"
    assert "not a medical device" in body["disclaimer"]
    uuid.UUID(body["prediction_id"])


async def test_prediction_appears_in_history(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    create_response = await client.post(
        ENDPOINT,
        files={"file": ("patch.png", _png_bytes(), "image/png")},
        headers=auth_tokens.auth_header,
    )
    prediction_id = create_response.json()["prediction_id"]

    history_response = await client.get(
        "/api/v1/predictions/history", headers=auth_tokens.auth_header
    )
    assert history_response.status_code == 200
    items = history_response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == prediction_id
    assert items[0]["status"] == "review_required"
    assert items[0]["decision"] == "review_required"
    assert items[0]["calibrated_probability"] == 0.5


async def test_prediction_detail_is_retrievable(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    create_response = await client.post(
        ENDPOINT,
        files={"file": ("patch.png", _png_bytes(), "image/png")},
        headers=auth_tokens.auth_header,
    )
    prediction_id = create_response.json()["prediction_id"]

    detail_response = await client.get(
        f"/api/v1/predictions/{prediction_id}", headers=auth_tokens.auth_header
    )
    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body["id"] == prediction_id
    assert body["model_id"] is not None
    assert body["input_sha256"] is not None


async def test_explanation_requested_returns_valid_base64_png(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    response = await client.post(
        ENDPOINT,
        files={"file": ("patch.png", _png_bytes(), "image/png")},
        data={"include_explanation": "true"},
        headers=auth_tokens.auth_header,
    )

    assert response.status_code == 201
    explanation = response.json()["explanation"]
    assert explanation["status"] == "available"
    assert explanation["encoding"] == "base64"

    import base64

    raw_png = base64.b64decode(explanation["data"])
    decoded = Image.open(io.BytesIO(raw_png))
    decoded.verify()


async def test_history_and_detail_never_return_explanation_image(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    create_response = await client.post(
        ENDPOINT,
        files={"file": ("patch.png", _png_bytes(), "image/png")},
        data={"include_explanation": "true"},
        headers=auth_tokens.auth_header,
    )
    explanation_b64 = create_response.json()["explanation"]["data"]
    prediction_id = create_response.json()["prediction_id"]
    assert explanation_b64

    history_response = await client.get(
        "/api/v1/predictions/history", headers=auth_tokens.auth_header
    )
    detail_response = await client.get(
        f"/api/v1/predictions/{prediction_id}", headers=auth_tokens.auth_header
    )

    assert explanation_b64 not in history_response.text
    assert explanation_b64 not in detail_response.text
    assert "explanation_status" in detail_response.json()
    assert detail_response.json()["explanation_status"] == "available"


async def test_client_reference_is_accepted_and_stored(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    response = await client.post(
        ENDPOINT,
        files={"file": ("patch.png", _png_bytes(), "image/png")},
        data={"client_reference": "demo-run-42"},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 201
    prediction_id = response.json()["prediction_id"]

    detail = await client.get(
        f"/api/v1/predictions/{prediction_id}", headers=auth_tokens.auth_header
    )
    assert detail.json()["client_reference"] == "demo-run-42"


async def test_empty_upload_rejected(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    response = await client.post(
        ENDPOINT,
        files={"file": ("empty.png", b"", "image/png")},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UPLOAD_EMPTY"


async def test_corrupted_image_rejected(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    response = await client.post(
        ENDPOINT,
        files={"file": ("bad.png", b"not a real image", "image/png")},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "IMAGE_DECODE_FAILED"


async def test_wrong_dimensions_rejected_in_strict_mode(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    response = await client.post(
        ENDPOINT,
        files={"file": ("patch.png", _png_bytes(size=64), "image/png")},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "IMAGE_DIMENSIONS_INVALID"


async def test_unsupported_format_rejected(client: AsyncClient, auth_tokens: AuthTokens) -> None:
    pixels = np.zeros((32, 32, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buffer, format="BMP")

    response = await client.post(
        ENDPOINT,
        files={"file": ("patch.bmp", buffer.getvalue(), "image/bmp")},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_IMAGE_FORMAT"


async def test_no_prediction_row_created_before_validation_succeeds(
    client: AsyncClient, auth_tokens: AuthTokens, db_session: AsyncSession
) -> None:
    response = await client.post(
        ENDPOINT,
        files={"file": ("bad.png", b"not a real image", "image/png")},
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 422
    assert await _count_predictions(db_session) == 0


async def test_model_unavailable_returns_structured_503(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    original = app.state.histopathology_model
    app.state.histopathology_model = None
    try:
        response = await client.post(
            ENDPOINT,
            files={"file": ("patch.png", _png_bytes(), "image/png")},
            headers=auth_tokens.auth_header,
        )
    finally:
        app.state.histopathology_model = original

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MODEL_NOT_READY"


async def test_inference_failure_marks_prediction_failed_without_leaking_internals(
    client: AsyncClient, auth_tokens: AuthTokens, db_session: AsyncSession
) -> None:
    active_model = app.state.histopathology_model
    original_predict = active_model.runtime.predict

    def _broken_predict(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("simulated catastrophic failure with /secret/path/leak")

    active_model.runtime.predict = _broken_predict  # type: ignore[method-assign]
    try:
        response = await client.post(
            ENDPOINT,
            files={"file": ("patch.png", _png_bytes(), "image/png")},
            headers=auth_tokens.auth_header,
        )
    finally:
        active_model.runtime.predict = original_predict  # type: ignore[method-assign]

    assert response.status_code == 500
    body = response.json()
    assert "/secret/path/leak" not in response.text
    assert body["error"]["code"] == "INFERENCE_FAILED"

    result = await db_session.execute(select(Prediction))
    predictions = result.scalars().all()
    assert len(predictions) == 1
    assert predictions[0].status.value == "failed"
    assert predictions[0].error_code == "INFERENCE_FAILED"
    assert predictions[0].safe_error_message is not None
    assert "/secret/path/leak" not in predictions[0].safe_error_message


async def test_user_cannot_access_another_users_prediction(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    create_response = await client.post(
        ENDPOINT,
        files={"file": ("patch.png", _png_bytes(), "image/png")},
        headers=auth_tokens.auth_header,
    )
    prediction_id = create_response.json()["prediction_id"]

    other_email = "other-user@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": other_email,
            "password": "correct-horse-battery-staple",
            "full_name": "Other",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": other_email, "password": "correct-horse-battery-staple"},
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.get(f"/api/v1/predictions/{prediction_id}", headers=other_headers)
    assert response.status_code == 404


async def test_nonexistent_prediction_returns_404(
    client: AsyncClient, auth_tokens: AuthTokens
) -> None:
    response = await client.get(
        f"/api/v1/predictions/{uuid.uuid4()}", headers=auth_tokens.auth_header
    )
    assert response.status_code == 404

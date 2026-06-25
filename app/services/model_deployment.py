"""Model deployment lifecycle: loads the configured bundle once at startup, records the
attempt in the `model_deployments` audit table, and hands back the resulting runtime (or
`None`) for the application to store on `app.state`. There is no hot-swapping - switching
models requires a process restart (see docs/model-deployment.md).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.prediction import PredictionModule
from app.repositories import model_deployment as deployment_repo
from medrisk_inference.bundle import load_bundle
from medrisk_inference.config import InferenceConfig
from medrisk_inference.exceptions import InferenceError
from medrisk_inference.runtime import HistopathologyModelRuntime

logger = logging.getLogger(__name__)


class ModelStartupError(Exception):
    """Raised when MODEL_REQUIRED=true and the model could not be loaded. The lifespan
    treats this as fatal and aborts application startup."""


@dataclass
class ActiveHistopathologyModel:
    runtime: HistopathologyModelRuntime
    deployment_id: uuid.UUID
    activated_at: datetime


def build_inference_config(settings: Settings) -> InferenceConfig:
    return InferenceConfig(
        environment=settings.ENVIRONMENT,
        model_bundle_path=settings.MODEL_BUNDLE_PATH,
        model_device=settings.MODEL_DEVICE,
        model_warmup_enabled=settings.MODEL_WARMUP_ENABLED,
        model_strict_version_check=settings.MODEL_STRICT_VERSION_CHECK,
        allow_synthetic_model=settings.ALLOW_SYNTHETIC_MODEL,
        inference_timeout_seconds=settings.INFERENCE_TIMEOUT_SECONDS,
        inference_queue_timeout_seconds=settings.INFERENCE_QUEUE_TIMEOUT_SECONDS,
        inference_max_concurrency=settings.INFERENCE_MAX_CONCURRENCY,
        max_upload_bytes=settings.MAX_UPLOAD_BYTES,
        max_image_width=settings.MAX_IMAGE_WIDTH,
        max_image_height=settings.MAX_IMAGE_HEIGHT,
        max_image_pixels=settings.MAX_IMAGE_PIXELS,
        min_image_width=settings.MIN_IMAGE_WIDTH,
        min_image_height=settings.MIN_IMAGE_HEIGHT,
        strict_model_input_shape=settings.STRICT_MODEL_INPUT_SHAPE,
        gradcam_enabled=settings.GRADCAM_ENABLED,
        gradcam_max_output_bytes=settings.GRADCAM_MAX_OUTPUT_BYTES,
    )


async def initialize_histopathology_deployment(
    session: AsyncSession, settings: Settings
) -> ActiveHistopathologyModel | None:
    """Validate + load the configured bundle and record the attempt. Returns `None` when no
    model ends up active (only ever permitted when `MODEL_REQUIRED=false`) - callers must
    not treat that as an error by itself.
    """
    config = build_inference_config(settings)

    if not config.model_bundle_path:
        if settings.MODEL_REQUIRED:
            raise ModelStartupError("MODEL_REQUIRED=true but MODEL_BUNDLE_PATH is not configured.")
        logger.warning(
            "No MODEL_BUNDLE_PATH configured - histopathology inference endpoints will "
            "return 503 until a model is configured."
        )
        return None

    try:
        bundle = load_bundle(config.model_bundle_path, config)
    except InferenceError as exc:
        logger.error("Model bundle failed validation: [%s] %s", exc.error_code, exc.message)
        if settings.MODEL_REQUIRED:
            raise ModelStartupError(str(exc)) from exc
        return None

    deployment = await deployment_repo.create(
        session,
        module=PredictionModule.HISTOPATHOLOGY,
        model_id=bundle.manifest.model_id,
        model_name=bundle.manifest.model_name,
        model_version=bundle.manifest.model_version,
        bundle_path=str(bundle.bundle_dir),
        bundle_sha256=bundle.bundle_sha256,
        architecture=bundle.manifest.architecture,
        dataset_name=bundle.manifest.dataset_name,
        dataset_mode=bundle.manifest.dataset_mode,
        synthetic_only=bundle.manifest.synthetic_only,
        eligible_for_demo=bundle.manifest.eligible_for_demo,
        device=settings.MODEL_DEVICE,
    )
    await session.commit()

    try:
        runtime = HistopathologyModelRuntime.from_bundle(bundle, config)
    except InferenceError as exc:
        await deployment_repo.mark_failed(session, deployment, failure_code=exc.error_code)
        await session.commit()
        logger.error("Model failed to load/warm up: [%s] %s", exc.error_code, exc.message)
        if settings.MODEL_REQUIRED:
            raise ModelStartupError(str(exc)) from exc
        return None

    health = runtime.health()
    await deployment_repo.mark_active(
        session,
        deployment,
        warmup_completed=health.warmup_completed,
        warmup_duration_ms=health.extra.get("warmup_duration_ms"),  # type: ignore[arg-type]
    )
    await deployment_repo.deactivate_previous_active(
        session, module=PredictionModule.HISTOPATHOLOGY, exclude_id=deployment.id
    )
    await session.commit()

    logger.info(
        "Histopathology model active: model_id=%s version=%s device=%s synthetic_only=%s",
        bundle.manifest.model_id,
        bundle.manifest.model_version,
        health.device,
        bundle.manifest.synthetic_only,
    )
    assert deployment.activated_at is not None  # set by mark_active(), just above
    return ActiveHistopathologyModel(
        runtime=runtime, deployment_id=deployment.id, activated_at=deployment.activated_at
    )

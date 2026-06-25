"""The in-process model runtime: owns the loaded PyTorch model and every other piece of
state needed to serve predictions (device, preprocessing transform, calibration, threshold,
review policy, warm-up/health status). Exactly one instance is built per process, at
application startup - see app/services/model_deployment.py - and never reloaded per request.

API routes never touch this class's `model` attribute directly; they go through
app/services/inference.py, which calls `predict()`/`explain()` and is the only thing
that knows how to map results into HTTP responses.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import torch
from PIL import Image
from torchvision import transforms as T

from medrisk_inference.bundle import LoadedBundle, load_bundle
from medrisk_inference.config import InferenceConfig
from medrisk_inference.decision import apply_calibration, decide, parse_review_policy, sigmoid
from medrisk_inference.exceptions import (
    BundleInvalidError,
    ExplanationFailedError,
    ExplanationNotSupportedError,
    ModelNotReadyError,
    ModelOutputInvalidError,
    ModelWarmupError,
)
from medrisk_inference.explanation import generate_explanation
from medrisk_inference.preprocessing import build_inference_transform, preprocess
from medrisk_inference.types import (
    DecisionResult,
    ExplanationResult,
    InferenceTimings,
    PreprocessedInput,
    RawModelOutput,
    RuntimeHealth,
    ValidatedImage,
)
from medrisk_ml.models.factory import build_model
from medrisk_ml.registry.manifest import ModelManifest
from medrisk_ml.utils.device import ResolvedDevice, resolve_device


@dataclass(frozen=True)
class PredictionOutcome:
    raw_output: RawModelOutput
    decision: DecisionResult
    processed: PreprocessedInput
    tensor: torch.Tensor  # retained only so an immediately-following explain() can reuse it
    timings: InferenceTimings


class HistopathologyModelRuntime:
    def __init__(
        self,
        *,
        model: torch.nn.Module,
        manifest: ModelManifest,
        device: ResolvedDevice,
        transform: T.Compose,
        calibration: dict[str, object] | None,
        bundle_sha256: str,
        config: InferenceConfig,
    ) -> None:
        self.model = model
        self.manifest = manifest
        self.device = device
        self.transform = transform
        self.calibration = calibration
        self.threshold = manifest.threshold
        self.review_policy = parse_review_policy(manifest.review_policy)
        self.bundle_sha256 = bundle_sha256
        self.config = config

        self._negative_class = next(c for c in manifest.class_names if c != manifest.positive_class)
        self._explain_lock = threading.Lock()
        self._warmup_completed = False
        self._warmup_duration_ms: float | None = None
        self._ready = False
        self._last_error_code: str | None = None

    @classmethod
    def load(cls, bundle_path: str, config: InferenceConfig) -> HistopathologyModelRuntime:
        bundle = load_bundle(bundle_path, config)
        return cls.from_bundle(bundle, config)

    @classmethod
    def from_bundle(
        cls, bundle: LoadedBundle, config: InferenceConfig
    ) -> HistopathologyModelRuntime:
        """Build a runtime from an already-validated bundle - lets callers (e.g. the model
        deployment service) read manifest metadata before committing to the full model
        load, without validating the bundle from disk twice."""
        resolved_device = resolve_device(config.model_device)

        model, _metadata = build_model(
            bundle.manifest.architecture,  # type: ignore[arg-type]
            pretrained=False,
            input_channels=bundle.manifest.input_channels,
            image_size=bundle.manifest.input_height,
        )
        state_dict = torch.load(
            bundle.bundle_dir / "model_state.pt", map_location="cpu", weights_only=True
        )
        try:
            model.load_state_dict(state_dict)
        except RuntimeError as exc:
            raise BundleInvalidError(
                f"model_state.pt is incompatible with architecture "
                f"{bundle.manifest.architecture!r}: {exc}"
            ) from exc

        model.to(resolved_device.device)
        model.eval()

        runtime = cls(
            model=model,
            manifest=bundle.manifest,
            device=resolved_device,
            transform=build_inference_transform(bundle.manifest),
            calibration=bundle.calibration,
            bundle_sha256=bundle.bundle_sha256,
            config=config,
        )
        if config.model_warmup_enabled:
            runtime.warmup()
        else:
            runtime._ready = True
        return runtime

    def warmup(self) -> None:
        started = time.perf_counter()
        try:
            dummy = torch.zeros(
                1,
                self.manifest.input_channels,
                self.manifest.input_height,
                self.manifest.input_width,
                device=self.device.device,
            )
            with torch.inference_mode():
                output = self.model(dummy)
            logit = self._extract_logit(output)
            apply_calibration(logit, self.calibration)
        except Exception as exc:
            self._ready = False
            self._warmup_completed = False
            self._last_error_code = "MODEL_WARMUP_FAILED"
            raise ModelWarmupError(f"Warm-up failed: {exc}") from exc

        self._warmup_completed = True
        self._warmup_duration_ms = (time.perf_counter() - started) * 1000
        self._ready = True
        self._last_error_code = None

    def predict(self, validated_image: ValidatedImage) -> PredictionOutcome:
        if not self._ready:
            raise ModelNotReadyError("Model runtime is not ready to serve predictions.")

        preprocessing_started = time.perf_counter()
        tensor, processed = preprocess(validated_image, self.transform)
        tensor = tensor.to(self.device.device)
        preprocessing_ms = (time.perf_counter() - preprocessing_started) * 1000

        inference_started = time.perf_counter()
        with torch.inference_mode():
            output = self.model(tensor)
        logit = self._extract_logit(output)
        inference_ms = (time.perf_counter() - inference_started) * 1000

        calibration_started = time.perf_counter()
        try:
            probability = apply_calibration(logit, self.calibration)
        except Exception as exc:
            self._last_error_code = "MODEL_OUTPUT_INVALID"
            raise ModelOutputInvalidError(f"Could not calibrate model output: {exc}") from exc
        decision_result = decide(
            probability,
            threshold=self.threshold,
            positive_class=self.manifest.positive_class,
            negative_class=self._negative_class,
            review_policy=self.review_policy,
        )
        calibration_ms = (time.perf_counter() - calibration_started) * 1000

        return PredictionOutcome(
            raw_output=RawModelOutput(logit=logit, raw_probability=sigmoid(logit)),
            decision=decision_result,
            processed=processed,
            tensor=tensor,
            timings=InferenceTimings(
                preprocessing_ms=preprocessing_ms,
                inference_ms=inference_ms,
                calibration_ms=calibration_ms,
            ),
        )

    def explain(
        self, outcome: PredictionOutcome, validated_image: ValidatedImage
    ) -> ExplanationResult:
        """Never raises: an explanation failure must never fail an otherwise-successful
        prediction, so failures here are reported as `ExplanationResult(status="failed")`
        rather than propagated - every caller gets this for free, not just the FastAPI layer.
        """
        if not self.config.gradcam_enabled:
            return ExplanationResult(status="disabled")

        base_image = Image.frombytes(
            validated_image.mode,
            (validated_image.width, validated_image.height),
            validated_image.rgb_image_bytes,
        ).resize((outcome.processed.processed_width, outcome.processed.processed_height))

        try:
            with self._explain_lock:
                return generate_explanation(
                    self.model,
                    self.manifest.architecture,
                    outcome.tensor,
                    base_image,
                    max_output_bytes=self.config.gradcam_max_output_bytes,
                )
        except (ExplanationFailedError, ExplanationNotSupportedError) as exc:
            return ExplanationResult(status="failed", error_code=exc.error_code)

    def health(self) -> RuntimeHealth:
        return RuntimeHealth(
            configured=True,
            bundle_verified=True,
            model_loaded=True,
            warmup_completed=self._warmup_completed,
            ready=self._ready,
            device=self.device.device.type,
            model_id=self.manifest.model_id,
            model_version=self.manifest.model_version,
            synthetic_only=self.manifest.synthetic_only,
            last_error_code=self._last_error_code,
            extra={"warmup_duration_ms": self._warmup_duration_ms},
        )

    def close(self) -> None:
        self._ready = False
        if self.device.device.type == "cuda":
            torch.cuda.empty_cache()

    @staticmethod
    def _extract_logit(output: torch.Tensor) -> float:
        if output.shape != (1, 1) or not torch.isfinite(output).all():
            raise ModelOutputInvalidError(
                f"Model produced an invalid output (shape={tuple(output.shape)})."
            )
        return float(output.reshape(-1)[0].item())

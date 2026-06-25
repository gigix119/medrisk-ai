"""Inference-domain exceptions.

Each carries a stable `error_code` (see docs/inference-architecture.md "Error codes") that
the FastAPI layer maps to an HTTP status and a safe, generic client-facing message. None of
these exceptions should ever surface a raw stack trace, tensor value, or filesystem path to
an API client - that mapping happens once, in app/core/exceptions.py.
"""

from __future__ import annotations

from typing import Any


class InferenceError(Exception):
    """Base class for all medrisk_inference exceptions."""

    error_code: str = "INFERENCE_FAILED"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class BundleInvalidError(InferenceError):
    """The configured model bundle failed validation (missing files, bad checksum,
    unsupported architecture, synthetic-in-production, symlink escape, ...)."""

    error_code = "MODEL_BUNDLE_INVALID"


class VersionIncompatibleError(InferenceError):
    error_code = "MODEL_VERSION_INCOMPATIBLE"


class ModelNotReadyError(InferenceError):
    """Raised when an inference is attempted before/without a loaded, warmed-up model."""

    error_code = "MODEL_NOT_READY"


class ModelWarmupError(InferenceError):
    error_code = "MODEL_WARMUP_FAILED"


class ImageValidationError(InferenceError):
    """Base class for upload/image-decoding failures. Subclasses set a specific code."""

    error_code = "IMAGE_DECODE_FAILED"


class ImageDecodeFailedError(ImageValidationError):
    error_code = "IMAGE_DECODE_FAILED"


class UploadEmptyError(ImageValidationError):
    error_code = "UPLOAD_EMPTY"


class UploadTooLargeError(ImageValidationError):
    error_code = "UPLOAD_TOO_LARGE"


class UnsupportedImageFormatError(ImageValidationError):
    error_code = "UNSUPPORTED_IMAGE_FORMAT"


class ImageDimensionsInvalidError(ImageValidationError):
    error_code = "IMAGE_DIMENSIONS_INVALID"


class ImagePixelLimitExceededError(ImageValidationError):
    error_code = "IMAGE_PIXEL_LIMIT_EXCEEDED"


class ImageMultiFrameNotSupportedError(ImageValidationError):
    error_code = "IMAGE_MULTIFRAME_NOT_SUPPORTED"


class ImageMimeMismatchError(ImageValidationError):
    error_code = "IMAGE_MIME_MISMATCH"


class ModelOutputInvalidError(InferenceError):
    error_code = "MODEL_OUTPUT_INVALID"


class CalibrationError(InferenceError):
    error_code = "CALIBRATION_FAILED"


class DecisionPolicyInvalidError(InferenceError):
    error_code = "DECISION_POLICY_INVALID"


class ExplanationNotSupportedError(InferenceError):
    error_code = "EXPLANATION_NOT_SUPPORTED"


class ExplanationFailedError(InferenceError):
    error_code = "EXPLANATION_FAILED"

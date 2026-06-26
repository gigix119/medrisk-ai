"""Domain/application exceptions.

These represent expected business-logic failures (a duplicate email, a bad
password, an expired token, ...). They carry no HTTP-specific concepts
themselves; the mapping to HTTP status codes happens once, centrally, in the
exception handlers registered in app.main.
"""

from typing import Any


class AppError(Exception):
    """Base class for all domain/application exceptions."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    default_message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
        error_code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details
        # Per-instance overrides: most subclasses rely on the class-level defaults, but the
        # inference layer maps many distinct medrisk_inference error codes onto a handful of
        # HTTP statuses, which is simpler as one class with dynamic code/status than as a
        # subclass per code.
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        self.headers = headers
        super().__init__(self.message)


class ConflictError(AppError):
    """Raised when an operation conflicts with existing state (e.g. duplicate email)."""

    status_code = 409
    error_code = "CONFLICT"
    default_message = "The request conflicts with existing data."


class AuthenticationError(AppError):
    """Raised when credentials or a token are missing, invalid, or unverifiable."""

    status_code = 401
    error_code = "AUTHENTICATION_FAILED"
    default_message = "Could not validate credentials."


class TokenExpiredError(AuthenticationError):
    """Raised when a JWT has a valid signature but has expired."""

    error_code = "TOKEN_EXPIRED"
    default_message = "The token has expired."


class TokenRevokedError(AuthenticationError):
    """Raised when a refresh token's session has been revoked or already rotated."""

    error_code = "TOKEN_REVOKED"
    default_message = "The token has been revoked."


class AuthorizationError(AppError):
    """Raised when an authenticated user is not allowed to perform an action."""

    status_code = 403
    error_code = "AUTHORIZATION_FAILED"
    default_message = "You do not have permission to perform this action."


class ResourceNotFoundError(AppError):
    """Raised when a requested resource does not exist (or is not visible to the caller)."""

    status_code = 404
    error_code = "NOT_FOUND"
    default_message = "The requested resource was not found."


class ServiceUnavailableError(AppError):
    """Raised when a required dependency (e.g. the database) is unreachable."""

    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"
    default_message = "A required service is temporarily unavailable."


class ModelNotConfiguredError(ServiceUnavailableError):
    """Raised when no model bundle path is configured at all (MODEL_REQUIRED=false)."""

    error_code = "MODEL_NOT_CONFIGURED"
    default_message = "No histopathology model is configured on this server."


class ModelUnavailableError(ServiceUnavailableError):
    """Raised when a model is configured but not currently loaded/ready (failed to load,
    still starting up, or a prior fatal runtime error marked it unhealthy)."""

    error_code = "MODEL_NOT_READY"
    default_message = "The histopathology model is not ready to serve predictions."


class InferenceQueueFullError(AppError):
    """Raised when the inference concurrency limiter's queue-wait timeout elapses."""

    status_code = 429
    error_code = "INFERENCE_QUEUE_FULL"
    default_message = "The inference queue is full. Please retry shortly."

    def __init__(self, message: str | None = None, *, retry_after_seconds: int = 1) -> None:
        super().__init__(message, headers={"Retry-After": str(retry_after_seconds)})


class InferenceTimeoutError(AppError):
    status_code = 504
    error_code = "INFERENCE_TIMEOUT"
    default_message = "The inference request exceeded its deadline."


class RateLimitExceededError(AppError):
    """Raised when a caller exceeds a per-endpoint rate limit (app.core.rate_limit).

    Limits are enforced per-process, not distributed - see docs/SECURITY_AUDIT.md.
    """

    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    default_message = "Too many requests. Please slow down and try again shortly."

    def __init__(self, message: str | None = None, *, retry_after_seconds: int = 60) -> None:
        super().__init__(message, headers={"Retry-After": str(retry_after_seconds)})

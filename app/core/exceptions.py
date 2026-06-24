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
        self, message: str | None = None, *, details: dict[str, Any] | None = None
    ) -> None:
        self.message = message or self.default_message
        self.details = details
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

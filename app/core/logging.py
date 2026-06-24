"""Logging configuration.

Uses the Python standard library only. Output is human-readable, but every
log line already carries the fields (timestamp, level, env, request id,
logger name) a JSON formatter would need later, so switching to structured
JSON logs in a future phase only means swapping the Formatter, not the
call sites.

Call sites must never log secrets: passwords, password hashes, JWTs,
Authorization headers, or database credentials.
"""

import logging
import sys
from contextvars import ContextVar

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str | None) -> None:
    """Bind the current request's ID so log records emitted during it can include it."""
    _request_id_ctx.set(request_id)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


class _RequestIdFilter(logging.Filter):
    """Injects the current request ID (if any) into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


def configure_logging(*, log_level: str, environment: str) -> None:
    """Configure the root logger. Safe to call once at application startup."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt=(
                f"%(asctime)s | %(levelname)-8s | env={environment} | "
                "req=%(request_id)s | %(name)s | %(message)s"
            ),
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    handler.addFilter(_RequestIdFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

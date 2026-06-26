"""Lightweight in-memory rate limiting for abuse-prone endpoints.

No external dependency (no slowapi/limits): a per-key sliding-window counter is enough for a
single-process deployment and mirrors the existing style of `app.state.inference_semaphore`
(app/main.py) - a small stdlib primitive rather than a new framework. Each Uvicorn worker
process keeps its own counters, so this provides no distributed guarantee across multiple
worker processes or replicas; that limitation is documented in docs/SECURITY_AUDIT.md, not
hidden.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable, Coroutine
from typing import Annotated

from fastapi import Depends, Request

from app.api.dependencies import SettingsDep
from app.core.config import Settings
from app.core.exceptions import RateLimitExceededError


class SlidingWindowRateLimiter:
    """Per-key sliding-window request counter.

    `now` is accepted as a parameter (defaulting to `time.monotonic()`) so unit tests can
    drive it deterministically instead of sleeping in real time.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, *, limit: int, window_seconds: float, now: float | None = None) -> None:
        """Record one hit for `key`; raises RateLimitExceededError if `limit` is exceeded
        within the trailing `window_seconds`."""
        current = now if now is not None else time.monotonic()
        hits = self._hits[key]
        cutoff = current - window_seconds
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = max(1, round(window_seconds - (current - hits[0])))
            raise RateLimitExceededError(retry_after_seconds=retry_after)
        hits.append(current)


def _client_key(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _build_dependency(
    limiter: SlidingWindowRateLimiter, *, limit_attr: str, scope: str
) -> Callable[[Request, Settings], Coroutine[None, None, None]]:
    async def _dependency(request: Request, settings: SettingsDep) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return
        limit = getattr(settings, limit_attr)
        limiter.hit(f"{scope}:{_client_key(request)}", limit=limit, window_seconds=60.0)

    return _dependency


# One limiter instance per scope: a login burst must not consume an inference caller's
# budget and vice versa, even from the same client address.
_login_limiter = SlidingWindowRateLimiter()
_register_limiter = SlidingWindowRateLimiter()
_inference_limiter = SlidingWindowRateLimiter()
_research_write_limiter = SlidingWindowRateLimiter()

enforce_login_rate_limit = _build_dependency(
    _login_limiter, limit_attr="RATE_LIMIT_LOGIN_PER_MINUTE", scope="login"
)
enforce_register_rate_limit = _build_dependency(
    _register_limiter, limit_attr="RATE_LIMIT_REGISTER_PER_MINUTE", scope="register"
)
enforce_inference_rate_limit = _build_dependency(
    _inference_limiter, limit_attr="RATE_LIMIT_INFERENCE_PER_MINUTE", scope="inference"
)
enforce_research_write_rate_limit = _build_dependency(
    _research_write_limiter,
    limit_attr="RATE_LIMIT_RESEARCH_WRITE_PER_MINUTE",
    scope="research-write",
)

LoginRateLimitDep = Annotated[None, Depends(enforce_login_rate_limit)]
RegisterRateLimitDep = Annotated[None, Depends(enforce_register_rate_limit)]
InferenceRateLimitDep = Annotated[None, Depends(enforce_inference_rate_limit)]
ResearchWriteRateLimitDep = Annotated[None, Depends(enforce_research_write_rate_limit)]

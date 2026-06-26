"""Unit tests for app.core.rate_limit.SlidingWindowRateLimiter.

Pure logic, no app/DB - the API-level wiring is intentionally not exercised here because
RATE_LIMIT_ENABLED=false for the whole integration test session (see tests/conftest.py);
this is the one place the actual limiting behaviour is verified.
"""

import pytest

from app.core.exceptions import RateLimitExceededError
from app.core.rate_limit import SlidingWindowRateLimiter


def test_hits_within_limit_do_not_raise() -> None:
    limiter = SlidingWindowRateLimiter()
    for i in range(5):
        limiter.hit("key", limit=5, window_seconds=60.0, now=float(i))


def test_hit_beyond_limit_raises_with_retry_after_header() -> None:
    limiter = SlidingWindowRateLimiter()
    for i in range(3):
        limiter.hit("key", limit=3, window_seconds=60.0, now=float(i))

    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.hit("key", limit=3, window_seconds=60.0, now=3.0)

    assert exc_info.value.status_code == 429
    assert "Retry-After" in (exc_info.value.headers or {})


def test_different_keys_have_independent_budgets() -> None:
    limiter = SlidingWindowRateLimiter()
    for i in range(3):
        limiter.hit("key-a", limit=3, window_seconds=60.0, now=float(i))

    # "key-b" must not be affected by "key-a" exhausting its budget.
    limiter.hit("key-b", limit=3, window_seconds=60.0, now=0.0)


def test_old_hits_fall_out_of_the_window() -> None:
    limiter = SlidingWindowRateLimiter()
    for i in range(3):
        limiter.hit("key", limit=3, window_seconds=10.0, now=float(i))

    # All three hits are now more than 10s in the past relative to now=20.0.
    limiter.hit("key", limit=3, window_seconds=10.0, now=20.0)

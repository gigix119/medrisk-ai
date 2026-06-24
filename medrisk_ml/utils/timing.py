"""Lightweight elapsed-time measurement for epoch/step duration tracking."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class Elapsed:
    """Mutable holder so callers can read the duration after the `with` block exits."""

    seconds: float = 0.0


@contextmanager
def timer() -> Iterator[Elapsed]:
    """Measure wall-clock time spent inside the ``with`` block.

    Usage::

        with timer() as t:
            do_work()
        print(t.seconds)
    """
    elapsed = Elapsed()
    start = time.perf_counter()
    try:
        yield elapsed
    finally:
        elapsed.seconds = time.perf_counter() - start

"""Consistent stream-logger configuration shared by the ML CLI, scripts, and engine."""

from __future__ import annotations

import logging

_CONFIGURED_LOGGERS: set[str] = set()

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str, level: int | str = logging.INFO) -> logging.Logger:
    """Return a configured logger, attaching a stream handler only once per name."""
    logger = logging.getLogger(name)
    if name not in _CONFIGURED_LOGGERS:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
        logger.addHandler(handler)
        logger.propagate = False
        _CONFIGURED_LOGGERS.add(name)
    logger.setLevel(level)
    return logger

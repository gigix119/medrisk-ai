"""Small standalone helpers (no torch/PIL dependency) shared across the package."""

from __future__ import annotations

import re

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_MAX_SAFE_FILENAME_LENGTH = 128


def sanitize_filename(filename: str | None) -> str | None:
    """Reduce an untrusted client-supplied filename to a short, safe display string.

    Strips any path components and control characters, and truncates the result. The
    output is never used to create a file on disk or as a database/cache key - only as
    optional display metadata. Returns `None` for an empty/missing filename.
    """
    if not filename:
        return None
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = _CONTROL_CHARS.sub("", basename).strip()
    if not cleaned:
        return None
    return cleaned[:_MAX_SAFE_FILENAME_LENGTH]

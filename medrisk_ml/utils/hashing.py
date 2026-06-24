"""Hashing helpers used for config fingerprints and checkpoint/bundle integrity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    """Full 64-char hex SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str, chunk_size: int = 1024 * 1024) -> str:
    """Full 64-char hex SHA-256 digest of a file's contents, streamed in chunks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json_dumps(obj: Any) -> str:
    """Canonical (sorted-key, separator-stable) JSON serialization for hashing."""
    return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))


def stable_hash(obj: Any, length: int = 16) -> str:
    """Short, stable, content-addressed id for a JSON-serializable object (e.g. a resolved config)."""
    full = sha256_bytes(stable_json_dumps(obj).encode("utf-8"))
    return full[:length]

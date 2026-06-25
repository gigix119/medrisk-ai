"""Canonical-JSON hashing for config/protocol fingerprints.

Deliberately a small, self-contained stdlib-only equivalent of
`medrisk_ml.utils.hashing.stable_json_dumps`/`sha256_bytes`, rather than importing that module
directly - `app` and `medrisk_ml` never import each other (see docs/architecture.md and
docs/PHASE_7_PROGRESS.md); only the offline `medrisk_research` CLI package is allowed to
import both.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    """Sorted-key, stable-separator JSON serialization, suitable for hashing."""
    return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))


def sha256_hexdigest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def config_hash(obj: Any) -> str:
    """Stable SHA-256 hex digest of a JSON-serializable object's canonical form - used for
    `ResearchStudy.configuration_hash` and any other config/protocol fingerprint."""
    return sha256_hexdigest(canonical_json(obj).encode("utf-8"))

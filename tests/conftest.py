"""Session-wide pytest setup.

ENVIRONMENT is forced to "test" before any app module is imported anywhere
in the test session, so the app's database engine targets TEST_DATABASE_URL
(a separate database from development - see app/db/session.py) rather than
whatever ENVIRONMENT happens to be set to in the developer's shell or .env.

Unit tests (tests/unit) import app.core.* modules but never touch the
database; DB- and HTTP-client fixtures live in tests/integration/conftest.py
so unit tests never pay for (or risk breaking on) a real DB connection.

A deterministic synthetic model bundle is built once here (also before any app import) and
MODEL_* env vars are pointed at it, so every integration test that spins up the app via
`LifespanManager` (tests/integration/conftest.py's `client` fixture) loads a real,
verified - if synthetic - histopathology model rather than running with none configured.
Its review_policy is deliberately set so the bundle's constant model output lands in
`review_required`; the negative/positive decision boundaries are exhaustively covered at
the unit level (tests/inference/test_decision.py) instead of needing several real model
loads here.
"""

import os
import tempfile
from pathlib import Path

os.environ["ENVIRONMENT"] = "test"

_MODEL_BUNDLE_DIR = Path(tempfile.mkdtemp(prefix="medrisk-test-bundle-"))

# Not underscore-prefixed: tests/integration/conftest.py imports this to write fixture
# images under the same root the app's Settings.DATASETS_ROOT is pointed at below.
TEST_DATASETS_ROOT = Path(tempfile.mkdtemp(prefix="medrisk-test-datasets-"))


def _build_integration_test_bundle() -> Path:
    from tests.inference.fixtures.builder import build_constant_output_bundle

    return build_constant_output_bundle(
        _MODEL_BUNDLE_DIR,
        model_name="integration-test-cnn",
        model_version="0.0.1-test",
        image_size=32,
        threshold=0.5,
        review_policy={"negative_probability_max": 0.3, "positive_probability_min": 0.7},
    )


os.environ["MODEL_BUNDLE_PATH"] = str(_build_integration_test_bundle())
os.environ["MODEL_REQUIRED"] = "true"
os.environ["MODEL_DEVICE"] = "cpu"
os.environ["MODEL_WARMUP_ENABLED"] = "true"
os.environ["GRADCAM_ENABLED"] = "true"
os.environ["ALLOW_SYNTHETIC_MODEL"] = "true"
os.environ["DATASETS_ROOT"] = str(TEST_DATASETS_ROOT)

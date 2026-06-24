"""Session-wide pytest setup.

ENVIRONMENT is forced to "test" before any app module is imported anywhere
in the test session, so the app's database engine targets TEST_DATABASE_URL
(a separate database from development - see app/db/session.py) rather than
whatever ENVIRONMENT happens to be set to in the developer's shell or .env.

Unit tests (tests/unit) import app.core.* modules but never touch the
database; DB- and HTTP-client fixtures live in tests/integration/conftest.py
so unit tests never pay for (or risk breaking on) a real DB connection.
"""

import os

os.environ["ENVIRONMENT"] = "test"

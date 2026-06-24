"""Wait for PostgreSQL to become reachable.

Used by Docker Compose before running migrations / starting the API, and
safe to run manually: `python -m scripts.wait_for_db`.

Exits 0 once the database accepts connections, or exits 1 after timing out.
Never logs the database URL itself (it contains credentials) - only the
hostname being polled.
"""

import asyncio
import logging
import sys
import time
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.db.session import get_database_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("wait_for_db")

MAX_WAIT_SECONDS = 30
RETRY_INTERVAL_SECONDS = 1.0


async def wait_for_db() -> bool:
    settings = get_settings()
    database_url = get_database_url(settings)
    host = urlsplit(database_url.replace("+asyncpg", "")).hostname or "unknown-host"

    engine = create_async_engine(database_url, pool_pre_ping=True)
    deadline = time.monotonic() + MAX_WAIT_SECONDS

    try:
        while time.monotonic() < deadline:
            try:
                async with engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
                logger.info("Database at host '%s' is reachable.", host)
                return True
            except Exception as exc:
                logger.info(
                    "Database at host '%s' not ready yet (%s). Retrying...",
                    host,
                    type(exc).__name__,
                )
                await asyncio.sleep(RETRY_INTERVAL_SECONDS)
    finally:
        await engine.dispose()

    logger.error(
        "Database at host '%s' did not become reachable within %s seconds.",
        host,
        MAX_WAIT_SECONDS,
    )
    return False


def main() -> None:
    success = asyncio.run(wait_for_db())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

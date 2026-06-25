"""Idempotently seed a local-development login account.

Used by Docker Compose (`compose.yaml`) after migrations, before Uvicorn starts. Safe to run
repeatedly - looks up the account by email first and never resets the password on an existing
row (a developer may have already changed it through the app). Always exits 0 on every
guard/no-op path; the only failure mode that should ever exit non-zero is a genuine DB error,
so the Compose `&&` command chain never blocks the API from starting.

Refuses to run when ENVIRONMENT=production (Settings itself fails startup if the two
DEV_SEED_USER_* variables are set in production - see app.core.config - so this script's own
production check is defense in depth, not the only guard) or when the two required
environment variables are not both set (a fresh clone with no customized .env seeds nothing
and prints no default credentials anywhere).
"""

import asyncio
import logging
import sys

from app.core.config import get_settings
from app.core.exceptions import ConflictError
from app.db.session import AsyncSessionLocal
from app.repositories import user as user_repo
from app.services.auth import register_user

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("seed_dev_user")


async def seed_dev_user() -> None:
    settings = get_settings()

    if settings.ENVIRONMENT == "production":
        logger.info("ENVIRONMENT=production - skipping dev user seed.")
        return

    email = settings.DEV_SEED_USER_EMAIL
    password = settings.DEV_SEED_USER_PASSWORD
    if not email or password is None:
        logger.info(
            "DEV_SEED_USER_EMAIL/DEV_SEED_USER_PASSWORD not both set - skipping dev user seed."
        )
        return

    async with AsyncSessionLocal() as session:
        existing = await user_repo.get_by_email(session, email.strip().lower())
        if existing is not None:
            logger.info("Dev user %s already exists, skipping.", email)
            return

        try:
            await register_user(
                session,
                email=email,
                password=password.get_secret_value(),
                full_name="Research Platform Reviewer",
            )
        except ConflictError:
            # Lost a race with another process seeding the same account concurrently - fine.
            logger.info("Dev user %s already exists, skipping.", email)
            return

    logger.info("Seeded dev user %s.", email)


def main() -> None:
    asyncio.run(seed_dev_user())
    sys.exit(0)


if __name__ == "__main__":
    main()

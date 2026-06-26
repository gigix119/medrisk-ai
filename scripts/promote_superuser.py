"""Operational CLI: grant or revoke administrator (`is_superuser`) status on an existing user.

This is a deliberate operator action, not automatic seeding (contrast with
scripts/seed_dev_user.py) - it runs in any environment, including production, because there
is currently no other way to create the first administrator account. The account must already
exist (register through the normal `/auth/register` flow first); this script never creates a
user or touches a password.

Usage:
    python -m scripts.promote_superuser user@example.com
    python -m scripts.promote_superuser user@example.com --revoke
"""

import argparse
import asyncio
import logging
import sys

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("promote_superuser")


async def set_superuser(email: str, *, is_superuser: bool) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email.strip().lower()))
        user = result.scalar_one_or_none()
        if user is None:
            logger.error("No user found with email %s. Register the account first.", email)
            return False
        if user.is_superuser == is_superuser:
            logger.info("User %s already has is_superuser=%s - no change.", email, is_superuser)
            return True
        user.is_superuser = is_superuser
        await session.commit()
        logger.info("Set is_superuser=%s for %s.", is_superuser, email)
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Email address of an already-registered user.")
    parser.add_argument(
        "--revoke",
        action="store_true",
        help="Revoke administrator status instead of granting it.",
    )
    args = parser.parse_args()

    ok = asyncio.run(set_superuser(args.email, is_superuser=not args.revoke))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

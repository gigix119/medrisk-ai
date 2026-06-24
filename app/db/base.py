"""Shared SQLAlchemy declarative base.

Alembic's autogenerate support compares the live database against
`Base.metadata`, so every ORM model must subclass this `Base` and be
imported (see app/models/__init__.py) before Alembic runs.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

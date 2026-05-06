"""SQLAlchemy declarative base (domain models added in later tickets)."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

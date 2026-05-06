"""FastAPI dependencies (database session; auth added in later tickets)."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from nativeforge.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

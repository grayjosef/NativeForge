"""Pytest configuration — file-backed SQLite plus Alembic before collection."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text

_tmp = Path(tempfile.mkdtemp(prefix="nf_pytest_"))
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{(_tmp / 'nf.sqlite3').as_posix()}"


def pytest_configure(config: pytest.Config) -> None:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(root / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    from nativeforge.lib.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _truncate_nf_tables() -> None:
    yield
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as s:
        s.execute(text("DELETE FROM nf_audit_events"))
        s.execute(text("DELETE FROM nf_review_artifacts"))
        s.execute(text("DELETE FROM organizations"))
        s.commit()

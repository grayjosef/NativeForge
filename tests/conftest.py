"""Pytest configuration — default in-memory SQLite for tests that touch the DB stack."""

import os

import pytest

from nativeforge.lib.settings import get_settings

# Before importing application modules that build the SQLAlchemy engine.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    """Clear settings lru_cache between tests (env may be monkeypatched)."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

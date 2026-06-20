"""Sprint 272: staging environment guard."""

from __future__ import annotations

import pytest

from nativeforge.lib.settings import get_settings
from nativeforge.services.staging_environment_guard_service import (
    build_staging_environment_contract,
    is_production_environment,
    is_staging_environment,
    require_staging_not_production,
)


@pytest.fixture
def staging_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    get_settings.cache_clear()


def test_staging_contract(staging_env: None) -> None:
    contract = build_staging_environment_contract()
    assert contract["is_staging"] is True
    assert contract["dry_run_allowed"] is True
    assert contract["never_production"] is True


def test_production_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_APP_ENV", "production")
    get_settings.cache_clear()
    assert is_production_environment() is True
    assert is_staging_environment() is False
    with pytest.raises(PermissionError, match="production"):
        require_staging_not_production()
    get_settings.cache_clear()

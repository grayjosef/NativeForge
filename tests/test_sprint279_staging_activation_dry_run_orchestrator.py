"""Sprint 279: staging activation dry-run orchestrator."""

from __future__ import annotations

import pytest

from nativeforge.lib.settings import get_settings
from nativeforge.services.staging_activation_dry_run_orchestrator_service import (
    run_staging_activation_dry_run,
)
from nativeforge.services.staging_tier1_dry_fetch_service import (
    reset_tier1_dry_fetch_rate_limit,
)


@pytest.fixture
def staging_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    get_settings.cache_clear()
    reset_tier1_dry_fetch_rate_limit()


def test_full_dry_run(staging_gates: None) -> None:
    result = run_staging_activation_dry_run()
    assert result["stop_before_activation"] is True
    assert result["no_source_activation_performed"] is True
    assert result["seed_preview_report"]["seed_row_count"] == 177
    assert result["tier1_dry_fetch"]["idempotent_path_verified"] is True

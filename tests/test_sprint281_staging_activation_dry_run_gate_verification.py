"""Sprint 281: staging activation dry-run gate verification."""

from __future__ import annotations

import pytest

from nativeforge.lib.settings import get_settings
from nativeforge.services.staging_activation_dry_run_gate_verification_service import (
    verify_staging_activation_dry_run_gates,
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


def test_gate_verification(staging_gates: None) -> None:
    result = verify_staging_activation_dry_run_gates()
    assert result["verification_passed"] is True

"""Sprint 273: staging activation dry-run plan gate."""

from __future__ import annotations

import pytest

from nativeforge.lib.settings import get_settings
from nativeforge.services.staging_activation_dry_run_gate_service import (
    build_staging_activation_dry_run_gate_contract,
    is_staging_activation_dry_run_approved,
    require_staging_activation_dry_run_gate,
)


@pytest.fixture
def staging_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    get_settings.cache_clear()


def test_dry_run_gate_approved(staging_gates: None) -> None:
    assert is_staging_activation_dry_run_approved(
        nf_live_source_ingestion=True,
        nf_staging_activation_dry_run=True,
    )
    contract = build_staging_activation_dry_run_gate_contract(
        nf_live_source_ingestion=True,
        nf_staging_activation_dry_run=True,
    )
    assert contract["dry_run_approved"] is True
    assert contract["no_source_activation"] is True


def test_dry_run_gate_missing_query_flag(staging_gates: None) -> None:
    with pytest.raises(PermissionError):
        require_staging_activation_dry_run_gate(
            nf_live_source_ingestion=False,
            nf_staging_activation_dry_run=True,
        )


def test_dry_run_gate_rejects_non_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_APP_ENV", "local")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    get_settings.cache_clear()
    assert is_staging_activation_dry_run_approved(
        nf_live_source_ingestion=True,
        nf_staging_activation_dry_run=True,
    ) is False
    get_settings.cache_clear()

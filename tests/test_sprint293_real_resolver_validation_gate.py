"""Sprint 293: real-resolver validation plan gate."""

from __future__ import annotations

import pytest

from nativeforge.lib.settings import get_settings
from nativeforge.services.real_resolver_validation_gate_service import (
    is_real_resolver_validation_approved,
)


@pytest.fixture
def staging_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    monkeypatch.setenv("NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED", "true")
    get_settings.cache_clear()


def test_validation_gate_approved(staging_gates: None) -> None:
    assert is_real_resolver_validation_approved(
        nf_live_source_ingestion=True,
        nf_real_resolver_validation=True,
    )

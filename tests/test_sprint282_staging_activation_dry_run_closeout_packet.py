"""Sprint 282: staging activation dry-run closeout packet."""

from __future__ import annotations

import json

import pytest

from nativeforge.lib.settings import get_settings
from nativeforge.services.staging_activation_dry_run_closeout_packet_service import (
    ARTIFACT_TYPE,
    build_staging_activation_dry_run_closeout_packet,
)
from nativeforge.services.staging_activation_dry_run_gate_verification_service import (
    verify_staging_activation_dry_run_gates,
)
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


def test_closeout_packet(staging_gates: None) -> None:
    gate = verify_staging_activation_dry_run_gates()
    reset_tier1_dry_fetch_rate_limit()
    dry_run = run_staging_activation_dry_run()
    packet = build_staging_activation_dry_run_closeout_packet(
        gate_verification=gate,
        dry_run=dry_run,
    )
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["gate_verification_passed"] is True
    assert packet["stop_before_activation"] is True
    json.dumps(packet)

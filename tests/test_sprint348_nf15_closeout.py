"""Sprint 348: NF-15 gate and closeout."""

from __future__ import annotations

import json

import pytest

from nativeforge.lib.settings import get_settings
from nativeforge.services.nf15_no_evidence_honesty_closeout_packet_service import (
    ARTIFACT_TYPE,
    build_nf15_no_evidence_honesty_closeout_packet,
)
from nativeforge.services.nf15_no_evidence_honesty_gate_verification_service import (
    verify_nf15_no_evidence_honesty_gates,
)


@pytest.fixture
def staging_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    monkeypatch.setenv("NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED", "true")
    get_settings.cache_clear()


def test_nf15_gate_and_closeout(staging_gates: None) -> None:
    gate = verify_nf15_no_evidence_honesty_gates()
    assert gate["verification_passed"] is True
    assert gate["checks"]["no_tribal_federal_in_irrelevant"] is True
    assert gate["checks"]["fed021_reingested"] is True
    packet = build_nf15_no_evidence_honesty_closeout_packet(gate_verification=gate)
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["block"] == "NF-15"
    json.dumps(packet)

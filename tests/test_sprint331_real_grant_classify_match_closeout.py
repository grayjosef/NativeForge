"""Sprint 331: NF-13 closeout and gate verification."""

from __future__ import annotations

import json

import pytest

from nativeforge.lib.settings import get_settings
from nativeforge.services.real_grant_classify_match_closeout_packet_service import (
    ARTIFACT_TYPE,
    build_real_grant_classify_match_closeout_packet,
)
from nativeforge.services.real_grant_classify_match_gate_verification_service import (
    verify_real_grant_classify_match_gates,
)


@pytest.fixture
def staging_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    monkeypatch.setenv("NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED", "true")
    get_settings.cache_clear()


def test_nf13_gate_and_closeout(staging_gates: None) -> None:
    gate = verify_real_grant_classify_match_gates()
    assert gate["verification_passed"] is True
    assert gate["label_distribution"]
    assert gate["matched_grant_count"] >= 1
    packet = build_real_grant_classify_match_closeout_packet(gate_verification=gate)
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["honest_labeling"] is True
    assert packet["from_real_source_text"] is True
    assert packet["stop_at_checkpoint"] is True
    json.dumps(packet)

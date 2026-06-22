"""Sprint 339: NF-14 closeout and gate verification."""

from __future__ import annotations

import json

import pytest

from nativeforge.lib.settings import get_settings
from nativeforge.services.mixed_corpus_discrimination_closeout_packet_service import (
    ARTIFACT_TYPE,
    build_mixed_corpus_discrimination_closeout_packet,
)
from nativeforge.services.mixed_corpus_discrimination_gate_verification_service import (
    verify_mixed_corpus_discrimination_gates,
)


@pytest.fixture
def staging_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    monkeypatch.setenv("NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED", "true")
    get_settings.cache_clear()


def test_nf14_gate_and_closeout(staging_gates: None) -> None:
    gate = verify_mixed_corpus_discrimination_gates()
    assert gate["verification_passed"] is True
    assert gate["distinct_label_count"] >= 6
    assert gate["tribe_eligible_broad_discoverable_count"] >= 1
    assert len(gate["worked_examples_per_label"]) == 8
    packet = build_mixed_corpus_discrimination_closeout_packet(gate_verification=gate)
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["block"] == "NF-14"
    assert packet["honest_labeling"] is True
    assert packet["stop_at_checkpoint"] is True
    json.dumps(packet)

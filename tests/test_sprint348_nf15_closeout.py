"""Sprint 348: NF-15 gate and closeout."""

from __future__ import annotations

import json

import pytest

from nativeforge.lib.settings import get_settings
from nativeforge.services.hermetic_test_guard_service import load_recorded_transport
from nativeforge.services.nf15_no_evidence_honesty_closeout_packet_service import (
    ARTIFACT_TYPE,
    build_nf15_no_evidence_honesty_closeout_packet,
)
from nativeforge.services.nf15_no_evidence_honesty_gate_verification_service import (
    verify_nf15_no_evidence_honesty_gates,
)

RECORDED_TRANSPORT = "nf_seed_2026_fed_021_samhsa_sm_26_024.json"


@pytest.fixture
def staging_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    monkeypatch.setenv("NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED", "true")
    get_settings.cache_clear()


def test_nf15_gate_and_closeout(staging_gates: None) -> None:
    # Gate 77B made live Grants.gov calls opt-in. This test must supply the
    # recorded transport rather than depend on the refused live path, which is
    # what left `fed021_reingested` false. The recording is the committed
    # SAMHSA SM-26-024 evidence for seed nf-seed-2026-fed-021.
    gate = verify_nf15_no_evidence_honesty_gates(
        http_post=load_recorded_transport(RECORDED_TRANSPORT)
    )
    assert gate["verification_passed"] is True
    assert gate["checks"]["no_tribal_federal_in_irrelevant"] is True
    assert gate["checks"]["fed021_reingested"] is True
    packet = build_nf15_no_evidence_honesty_closeout_packet(gate_verification=gate)
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["block"] == "NF-15"
    json.dumps(packet)

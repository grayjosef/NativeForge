"""Sprint 352-355: NF-16 no-proxy honesty gate and corpus."""

from __future__ import annotations

import json

import pytest

from nativeforge.lib.settings import get_settings
from nativeforge.services.nf16_no_proxy_corpus_classification_service import (
    classify_nf16_no_proxy_corpus,
)
from nativeforge.services.nf16_no_proxy_honesty_closeout_packet_service import (
    ARTIFACT_TYPE,
    build_nf16_no_proxy_honesty_closeout_packet,
)
from nativeforge.services.nf16_no_proxy_honesty_gate_verification_service import (
    verify_nf16_no_proxy_honesty_gates,
)


@pytest.fixture
def staging_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    monkeypatch.setenv("NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED", "true")
    get_settings.cache_clear()


def test_nf16_corpus_zero_proxy() -> None:
    result = classify_nf16_no_proxy_corpus()
    assert result["zero_proxy_substitutions"] is True
    assert result["no_tribal_federal_in_irrelevant"] is True
    assert result["no_live_nofo_never_irrelevant"] is True
    assert "nf13-real-fed-025" in result["no_live_nofo_grants"]


def test_nf16_gate_and_closeout(staging_gates: None) -> None:
    gate = verify_nf16_no_proxy_honesty_gates()
    assert gate["verification_passed"] is True
    assert gate["checks"]["zero_proxy_substitutions"] is True
    assert gate["checks"]["fed025_no_live_nofo"] is True
    packet = build_nf16_no_proxy_honesty_closeout_packet(gate_verification=gate)
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["block"] == "NF-16"
    json.dumps(packet)

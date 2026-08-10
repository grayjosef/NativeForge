"""Sprint 41: NM/WA classify+match closeout packet."""

from __future__ import annotations

from nativeforge.services.nm_wa_classify_match_closeout_packet_service import (
    build_nm_wa_classify_match_closeout_packet,
)

_GRANTS = [
    {
        "grant_id": "close-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_closeout_packet_core_flags() -> None:
    pkt = build_nm_wa_classify_match_closeout_packet(
        grants=_GRANTS, head_before="c26d33a", head_after="pending"
    )
    assert pkt["nm_wired"] is True
    assert pkt["wa_wired"] is True
    assert pkt["pushed"] is False
    assert pkt["live_ingestion"] is False
    assert pkt["source_activation"] is False
    assert pkt["hard_invariants"]["no_final_claim_without_evidence"] is True

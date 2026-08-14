"""Sprint 041: operator surfacing closeout packet."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_closeout_packet_service import (
    build_operator_surfacing_closeout_packet,
)

_G = [
    {
        "grant_id": "os-c-041",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_closeout_packet_flags() -> None:
    pkt = build_operator_surfacing_closeout_packet(
        grants=_G, head_before="392da8f", head_after="pending"
    )
    assert pkt["nm_operator_surfacing_built"] is True
    assert pkt["wa_operator_surfacing_built"] is True
    assert pkt["combined_review_queue_built"] is True
    assert pkt["scoring_match_logic_changed"] is False
    assert pkt["pushed"] is False
    assert all(pkt["hard_invariants"].values())

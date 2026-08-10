"""Sprint 043: closeout hard invariant coverage."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_closeout_packet_service import (
    build_operator_surfacing_closeout_packet,
)

_G = [{"grant_id": "os-c-043", "opportunity_title": "Tribal Discretionary Grant", "program_area": "health", "recognition_requirement": "federal_required"}]


def test_closeout_hard_invariants() -> None:
    pkt = build_operator_surfacing_closeout_packet(grants=_G)
    inv = pkt["hard_invariants"]
    assert inv["no_final_claim_without_evidence"] is True
    assert inv["missing_data_shown_not_hidden"] is True
    assert inv["next_check_present_when_review_required"] is True
    assert inv["no_scoring_match_logic_change"] is True

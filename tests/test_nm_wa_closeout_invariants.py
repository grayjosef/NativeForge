"""Sprint 42: closeout packet hard invariant coverage."""

from __future__ import annotations

from nativeforge.services.nm_wa_classify_match_closeout_packet_service import (
    build_nm_wa_classify_match_closeout_packet,
)

_GRANTS = [
    {
        "grant_id": "cinv-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_closeout_hard_invariants_all_true() -> None:
    pkt = build_nm_wa_classify_match_closeout_packet(grants=_GRANTS)
    inv = pkt["hard_invariants"]
    assert all(inv.values())
    assert pkt["rollup"]["final_eligibility_claim_allowed"] is False
    assert pkt["rollup"]["unknown_data_never_dropped"] is True

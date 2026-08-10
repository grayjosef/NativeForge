"""Sprint 47: final invariant suite aggregator marker."""

from __future__ import annotations

from nativeforge.services.nm_wa_classify_match_closeout_packet_service import (
    build_nm_wa_classify_match_closeout_packet,
)
from nativeforge.services.nm_wa_validation_rollup_service import (
    list_nm_wa_block_test_files,
)


def test_final_invariant_suite_marker() -> None:
    files = list_nm_wa_block_test_files()
    assert "test_nm_pilot_invariants.py" in files
    assert "test_wa_pilot_invariants.py" in files
    assert "test_nm_wa_rollup_invariants.py" in files
    assert "test_nm_wa_closeout_invariants.py" in files
    pkt = build_nm_wa_classify_match_closeout_packet(
        grants=[
            {
                "grant_id": "fin-001",
                "opportunity_title": "Tribal Discretionary Grant",
                "program_area": "health",
                "recognition_requirement": "federal_required",
            }
        ]
    )
    assert all(pkt["hard_invariants"].values())

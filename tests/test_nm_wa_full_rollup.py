"""Sprint 26: full NM/WA rollup composition."""

from __future__ import annotations

from nativeforge.services.nm_wa_pilot_rollup_service import run_nm_wa_pilot_full_rollup

_GRANTS = [
    {
        "grant_id": "full-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_full_rollup_includes_all_layers() -> None:
    full = run_nm_wa_pilot_full_rollup(grants=_GRANTS)
    assert full["offline_only"] is True
    assert full["live_ingestion"] is False
    assert full["source_activation"] is False
    assert "batch_summary" in full
    assert "readiness" in full
    assert "missing_data" in full
    assert "provenance" in full
    assert full["readiness"]["final_eligibility_claim_allowed"] is False

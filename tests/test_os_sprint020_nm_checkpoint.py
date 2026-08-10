"""Sprint 020: NM operator surfacing checkpoint."""

from __future__ import annotations

from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_surfacing_report,
)

_G = [
    {
        "grant_id": "os-nm-t020",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_nm_checkpoint() -> None:
    r = build_nm_operator_surfacing_report(grants=_G)
    assert r["total_profiles"] == 22
    assert r["rollup"]["all_discoverable"] is True
    assert r["rollup"]["conservative_no_final_claim_count"] == 22

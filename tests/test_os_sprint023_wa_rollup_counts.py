"""Sprint 023: WA operator rollup summary counts."""

from __future__ import annotations

from nativeforge.services.wa_operator_surfacing_report_service import (
    build_wa_operator_surfacing_report,
)

_G = [
    {
        "grant_id": "os-wa-t023",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_wa_rollup_counts() -> None:
    rollup = build_wa_operator_surfacing_report(grants=_G)["rollup"]
    assert rollup["total_profiles"] == 29
    assert rollup["needs_operator_review_count"] == 29
    assert rollup["conservative_no_final_claim_count"] == 29
    assert rollup["review_ready_count"] == 0

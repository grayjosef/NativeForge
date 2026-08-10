"""Sprint 013: NM operator rollup summary counts."""

from __future__ import annotations

from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_surfacing_report,
)

_G = [
    {
        "grant_id": "os-nm-t013",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_nm_rollup_counts() -> None:
    rollup = build_nm_operator_surfacing_report(grants=_G)["rollup"]
    assert rollup["total_profiles"] == 22
    assert rollup["needs_operator_review_count"] == 22
    assert rollup["conservative_no_final_claim_count"] == 22
    assert rollup["review_ready_count"] == 0
    assert rollup["all_human_review_required"] is True

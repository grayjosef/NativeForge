"""Sprint 032: combined NM/WA operator rollup summary."""

from __future__ import annotations

from nativeforge.services.nm_wa_combined_operator_surfacing_service import (
    build_combined_operator_rollup,
)

_G = [
    {
        "grant_id": "os-c-032",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_combined_rollup() -> None:
    r = build_combined_operator_rollup(grants=_G)
    assert r["nm_count"] == 22 and r["wa_count"] == 29
    assert r["combined_review_needed_count"] == 51
    assert r["final_eligibility_claim_allowed"] is False

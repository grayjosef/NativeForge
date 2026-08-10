"""Sprint 015: NM report never allows final eligibility claim."""

from __future__ import annotations

from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_surfacing_report,
)

_G = [
    {
        "grant_id": "os-nm-t015",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_nm_no_final_eligibility_claim() -> None:
    report = build_nm_operator_surfacing_report(grants=_G)
    assert all(r["final_eligibility_claim_allowed"] is False for r in report["rows"])

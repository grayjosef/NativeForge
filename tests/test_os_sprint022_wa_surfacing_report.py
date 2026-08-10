"""Sprint 022: WA operator surfacing report builder."""

from __future__ import annotations

from nativeforge.services.wa_operator_surfacing_report_service import (
    build_wa_operator_surfacing_report,
)

_G = [
    {
        "grant_id": "os-wa-t022",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_wa_surfacing_report_basics() -> None:
    report = build_wa_operator_surfacing_report(grants=_G)
    assert report["state_cohort"] == "WA"
    assert report["total_profiles"] == 29
    assert report["does_not_alter_classify_match_logic"] is True
    assert len(report["rows"]) == 29

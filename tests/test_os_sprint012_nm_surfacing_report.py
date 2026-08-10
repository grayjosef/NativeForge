"""Sprint 012: NM operator surfacing report builder."""

from __future__ import annotations

from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_surfacing_report,
)

_G = [
    {
        "grant_id": "os-nm-t012",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_nm_surfacing_report_basics() -> None:
    report = build_nm_operator_surfacing_report(grants=_G)
    assert report["state_cohort"] == "NM"
    assert report["total_profiles"] == 22
    assert report["does_not_alter_classify_match_logic"] is True
    assert report["live_ingestion"] is False
    assert len(report["rows"]) == 22

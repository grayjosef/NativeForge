"""Sprint 016: NM operator next-check present when review required."""

from __future__ import annotations

from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_surfacing_report,
)

_G = [
    {
        "grant_id": "os-nm-t016",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_nm_next_check_when_review_required() -> None:
    report = build_nm_operator_surfacing_report(grants=_G)
    for row in report["rows"]:
        assert row["human_review_required"] is True
        assert row["operator_next_check"]

"""Sprint 027: WA operator next-check present when review required."""

from __future__ import annotations

from nativeforge.services.wa_operator_surfacing_report_service import (
    build_wa_operator_surfacing_report,
)

_G = [{"grant_id": "os-wa-t027", "opportunity_title": "Tribal Discretionary Grant", "program_area": "health", "recognition_requirement": "federal_required"}]


def test_wa_next_check() -> None:
    report = build_wa_operator_surfacing_report(grants=_G)
    for row in report["rows"]:
        assert row["human_review_required"] is True
        assert row["operator_next_check"]

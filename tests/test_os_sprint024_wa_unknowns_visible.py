"""Sprint 024: WA unknowns/incomplete remain discoverable."""

from __future__ import annotations

from nativeforge.services.wa_operator_surfacing_report_service import (
    build_wa_operator_surfacing_report,
)

_G = [
    {
        "grant_id": "os-wa-t024",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "education",
        "recognition_requirement": "federal_required",
    }
]


def test_wa_unknowns_remain_visible() -> None:
    report = build_wa_operator_surfacing_report(grants=_G)
    assert report["rollup"]["all_discoverable"] is True
    assert len(report["rows"]) == 29

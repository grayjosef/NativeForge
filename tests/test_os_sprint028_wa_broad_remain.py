"""Sprint 028: WA broad/partial candidates remain visible despite missing data."""

from __future__ import annotations

from nativeforge.services.wa_operator_surfacing_report_service import (
    build_wa_operator_surfacing_report,
)

_G = [{"grant_id": "os-wa-t028", "opportunity_title": "Tribal Discretionary Grant", "program_area": "health", "recognition_requirement": "federal_required"}]


def test_wa_all_profiles_remain_visible() -> None:
    report = build_wa_operator_surfacing_report(grants=_G)
    assert report["total_profiles"] == 29
    assert report["rollup"]["all_discoverable"] is True

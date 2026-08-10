"""Sprint 030: WA operator surfacing checkpoint."""

from __future__ import annotations

from nativeforge.services.wa_operator_surfacing_report_service import (
    build_wa_operator_surfacing_report,
)

_G = [{"grant_id": "os-wa-t030", "opportunity_title": "Tribal Discretionary Grant", "program_area": "health", "recognition_requirement": "federal_required"}]


def test_wa_checkpoint() -> None:
    r = build_wa_operator_surfacing_report(grants=_G)
    assert r["total_profiles"] == 29
    assert r["rollup"]["all_discoverable"] is True

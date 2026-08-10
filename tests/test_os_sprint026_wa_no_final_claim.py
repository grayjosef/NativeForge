"""Sprint 026: WA report never allows final eligibility claim."""

from __future__ import annotations

from nativeforge.services.wa_operator_surfacing_report_service import (
    build_wa_operator_surfacing_report,
)

_G = [{"grant_id": "os-wa-t026", "opportunity_title": "Tribal Discretionary Grant", "program_area": "health", "recognition_requirement": "federal_required"}]


def test_wa_no_final_claim() -> None:
    report = build_wa_operator_surfacing_report(grants=_G)
    assert all(r["final_eligibility_claim_allowed"] is False for r in report["rows"])

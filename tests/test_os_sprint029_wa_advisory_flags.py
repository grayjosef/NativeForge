"""Sprint 029: WA surfacing advisory offline flags."""

from __future__ import annotations

from nativeforge.services.wa_operator_surfacing_report_service import (
    build_wa_operator_surfacing_report,
)

_G = [{"grant_id": "os-wa-t029", "opportunity_title": "Tribal Discretionary Grant", "program_area": "health", "recognition_requirement": "federal_required"}]


def test_wa_advisory_flags() -> None:
    r = build_wa_operator_surfacing_report(grants=_G)
    assert r["offline_only"] is True and r["source_activation"] is False

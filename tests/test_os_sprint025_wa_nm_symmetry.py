"""Sprint 025: WA report structure mirrors NM while preserving WA counts."""

from __future__ import annotations

from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_surfacing_report,
)
from nativeforge.services.wa_operator_surfacing_report_service import (
    build_wa_operator_surfacing_report,
)

_G = [
    {
        "grant_id": "os-sym-025",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_wa_nm_rollup_keys_symmetric() -> None:
    nm = build_nm_operator_surfacing_report(grants=_G)
    wa = build_wa_operator_surfacing_report(grants=_G)
    assert set(nm["rollup"].keys()) == set(wa["rollup"].keys())
    assert nm["total_profiles"] == 22
    assert wa["total_profiles"] == 29

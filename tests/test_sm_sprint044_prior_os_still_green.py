"""Sprint 044: prior operator surfacing builders still importable/green."""

from __future__ import annotations

from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_surfacing_report,
)
from nativeforge.services.nm_wa_combined_operator_surfacing_service import (
    build_combined_operator_review_queue,
)
from nativeforge.services.wa_operator_surfacing_report_service import (
    build_wa_operator_surfacing_report,
)

_G = [
    {
        "grant_id": "sm-044",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_prior_os_builders_still_green() -> None:
    nm = build_nm_operator_surfacing_report(grants=_G)
    wa = build_wa_operator_surfacing_report(grants=_G)
    q = build_combined_operator_review_queue(grants=_G)
    assert nm["total_profiles"] == 22
    assert wa["total_profiles"] == 29
    assert q["combined_profile_count"] == 51

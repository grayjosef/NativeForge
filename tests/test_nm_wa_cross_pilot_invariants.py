"""Sprint 40: cross-pilot invariants — NM/WA review forced; no live flags."""

from __future__ import annotations

from nativeforge.services.matching_profile_selector_service import (
    list_available_matching_profiles,
)
from nativeforge.services.nm_wa_operator_review_service import (
    build_fixture_coverage_report,
    build_operator_review_queue,
)

_GRANTS = [
    {
        "grant_id": "xinv-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_cross_pilot_selector_includes_nm_wa() -> None:
    keys = [p["fixture_key"] for p in list_available_matching_profiles()]
    assert any(str(k).startswith("nm_pilot_") for k in keys)
    assert any(str(k).startswith("wa_pilot_") for k in keys)


def test_cross_pilot_queue_and_coverage_invariants() -> None:
    coverage = build_fixture_coverage_report()
    assert coverage["NM"]["complete"] and coverage["WA"]["complete"]
    queue = build_operator_review_queue(grants=_GRANTS)
    assert queue["offline_only"] is True
    assert queue["all_require_operator_review"] is True

"""Sprint 29: missing-data report gap_count is consistent with gaps list."""

from __future__ import annotations

from nativeforge.services.nm_wa_pilot_rollup_service import build_missing_data_report

_GRANTS = [
    {
        "grant_id": "gapc-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_gap_count_matches_gaps_list() -> None:
    report = build_missing_data_report(grants=_GRANTS)
    assert report["gap_count"] == len(report["gaps"])

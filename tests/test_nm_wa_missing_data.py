"""Sprint 24: missing/unknown profile data remains discoverable."""

from __future__ import annotations

from nativeforge.services.nm_wa_pilot_rollup_service import build_missing_data_report

_GRANTS = [
    {
        "grant_id": "miss-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "education",
        "recognition_requirement": "federal_required",
    }
]


def test_missing_data_gaps_force_review_and_stay_visible() -> None:
    report = build_missing_data_report(grants=_GRANTS)
    assert report["unknown_data_never_dropped"] is True
    for gap in report["gaps"]:
        assert gap["remains_in_classify_match_outputs"] is True
        assert gap["forces_operator_review"] is True
        assert gap["missing_fields"]

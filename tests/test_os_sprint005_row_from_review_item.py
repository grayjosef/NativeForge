"""Sprint 005: build operator report row from review item."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_row_mapper_service import (
    build_operator_report_row_from_review_item,
)


def test_row_from_review_item_exposes_missing_and_next_check() -> None:
    row = build_operator_report_row_from_review_item(
        {
            "state": "NM",
            "profile_fixture_key": "nm_pilot_demo",
            "organization_name": "Demo Nation",
            "readiness_label": "incomplete_profile_data",
        },
        missing_fields=["program_areas"],
    )
    assert row["missing_data"] == ["program_areas"]
    assert row["human_review_required"] is True
    assert row["operator_next_check"]
    assert row["final_eligibility_claim_allowed"] is False
    assert row["discoverability"] == "visible_in_operator_review"

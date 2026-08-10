"""Sprint 002: empty conservative operator report row."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_report_schema_service import (
    empty_operator_report_row,
)


def test_empty_row_never_allows_final_claim() -> None:
    row = empty_operator_report_row(profile_id="nm_pilot_x", state_cohort="NM")
    assert row["final_eligibility_claim_allowed"] is False
    assert row["human_review_required"] is True
    assert row["discoverability"] == "visible_in_operator_review"
    assert row["profile_id"] == "nm_pilot_x"
    assert row["state_cohort"] == "NM"

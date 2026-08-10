"""Sprint 003: validate operator report row invariants."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_report_schema_service import (
    empty_operator_report_row,
    validate_operator_report_row,
)


def test_valid_empty_row_has_no_failures() -> None:
    row = empty_operator_report_row(profile_id="wa_pilot_x", state_cohort="WA")
    assert validate_operator_report_row(row) == []


def test_final_claim_true_fails_validation() -> None:
    row = empty_operator_report_row(profile_id="nm_pilot_x", state_cohort="NM")
    row["final_eligibility_claim_allowed"] = True
    failures = validate_operator_report_row(row)
    assert "final_eligibility_claim_not_allowed_without_evidence" in failures


def test_human_review_without_next_check_fails() -> None:
    row = empty_operator_report_row(profile_id="nm_pilot_x", state_cohort="NM")
    row["operator_next_check"] = []
    failures = validate_operator_report_row(row)
    assert "operator_next_check_required_when_human_review_required" in failures

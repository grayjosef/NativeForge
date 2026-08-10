"""Sprint 008: blockers expose review reasons for operator visibility."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_row_mapper_service import (
    build_operator_report_row_from_review_item,
)


def test_blockers_include_no_final_claim_reason() -> None:
    row = build_operator_report_row_from_review_item(
        {
            "state": "WA",
            "profile_fixture_key": "wa_pilot_d",
            "readiness_label": "needs_operator_review",
        },
        missing_fields=["program_areas", "grant_posture"],
    )
    assert "no_final_eligibility_without_explicit_evidence" in row["blockers"]
    assert "unknown_program_areas" in row["blockers"]
    assert "unknown_grant_posture" in row["blockers"]

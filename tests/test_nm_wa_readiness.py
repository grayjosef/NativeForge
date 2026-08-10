"""Sprint 23: conservative readiness labels never final-claim."""

from __future__ import annotations

from nativeforge.services.nm_wa_pilot_rollup_service import (
    READINESS_INCOMPLETE_PROFILE,
    READINESS_NEEDS_OPERATOR_REVIEW,
    assign_conservative_readiness_label,
    build_conservative_readiness_report,
)

_GRANTS = [
    {
        "grant_id": "ready-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_readiness_never_allows_final_claim() -> None:
    report = build_conservative_readiness_report(grants=_GRANTS)
    assert report["final_eligibility_claim_allowed"] is False
    assert report["all_require_operator_review"] is True
    for state in ("NM", "WA"):
        assert report["per_state"][state]
        assert all(
            row["final_eligibility_claim_allowed"] is False
            for row in report["per_state"][state]
        )


def test_assign_readiness_unknown_program_areas() -> None:
    label = assign_conservative_readiness_label(
        {"program_areas_unknown": True, "grant_posture": "mixed"}
    )
    assert label == READINESS_INCOMPLETE_PROFILE


def test_assign_readiness_complete_still_needs_review() -> None:
    label = assign_conservative_readiness_label(
        {"program_areas_unknown": False, "grant_posture": "mixed"}
    )
    assert label == READINESS_NEEDS_OPERATOR_REVIEW

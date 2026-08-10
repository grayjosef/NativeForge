"""Sprint 30: shared rollup hard invariants."""

from __future__ import annotations

from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_NEEDS_OPERATOR_REVIEW,
)
from nativeforge.services.nm_wa_pilot_rollup_service import run_nm_wa_pilot_full_rollup

_GRANTS = [
    {
        "grant_id": "inv-rollup-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_rollup_invariants_no_final_claim_and_review_forced() -> None:
    full = run_nm_wa_pilot_full_rollup(grants=_GRANTS)
    assert full["live_ingestion"] is False
    assert full["source_activation"] is False
    assert full["readiness"]["final_eligibility_claim_allowed"] is False
    assert full["batch_summary"]["all_needs_operator_review"] is True
    assert full["missing_data"]["unknown_data_never_dropped"] is True
    for state_rows in full["readiness"]["per_state"].values():
        assert all(
            row["match_label"] == LABEL_NEEDS_OPERATOR_REVIEW for row in state_rows
        )

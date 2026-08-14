"""Sprint 040: combined operator surfacing checkpoint."""

from __future__ import annotations

from nativeforge.services.nm_wa_combined_operator_surfacing_service import (
    build_combined_operator_review_queue,
)

_G = [
    {
        "grant_id": "os-c-040",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_combined_checkpoint() -> None:
    q = build_combined_operator_review_queue(grants=_G)
    assert q["combined_profile_count"] == 51
    assert q["combined_review_needed_count"] == 51
    assert q["final_eligibility_claim_allowed"] is False

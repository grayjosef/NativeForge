"""Sprint 031: combined NM/WA operator review queue."""

from __future__ import annotations

from nativeforge.services.nm_wa_combined_operator_surfacing_service import (
    build_combined_operator_review_queue,
)

_G = [{"grant_id": "os-c-031", "opportunity_title": "Tribal Discretionary Grant", "program_area": "health", "recognition_requirement": "federal_required"}]


def test_combined_queue_counts() -> None:
    q = build_combined_operator_review_queue(grants=_G)
    assert q["nm_count"] == 22
    assert q["wa_count"] == 29
    assert q["combined_profile_count"] == 51
    assert q["final_eligibility_claim_allowed"] is False
    assert q["does_not_alter_classify_match_logic"] is True

"""Sprint 31: operator review queue metadata."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_review_service import build_operator_review_queue

_GRANTS = [
    {
        "grant_id": "oq-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_operator_review_queue_covers_nm_wa() -> None:
    queue = build_operator_review_queue(grants=_GRANTS)
    assert queue["offline_only"] is True
    assert queue["all_require_operator_review"] is True
    assert queue["item_count"] == 22 + 29
    assert all(i["final_eligibility_claim_allowed"] is False for i in queue["items"])

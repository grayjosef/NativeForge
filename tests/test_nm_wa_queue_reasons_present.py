"""Sprint 36: every queue item carries review reasons and next checks."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_review_service import build_operator_review_queue

_GRANTS = [
    {
        "grant_id": "qr-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_every_queue_item_has_reasons_and_checks() -> None:
    queue = build_operator_review_queue(grants=_GRANTS)
    assert queue["items"]
    for item in queue["items"]:
        assert item["review_reasons"]
        assert item["next_checks"]

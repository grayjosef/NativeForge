"""Sprint 173: operator-approved duplicate detection."""

from __future__ import annotations

from nativeforge.services.funding_opportunity_intake_operator_duplicate_detection_service import (
    apply_operator_duplicate_approval,
    detect_operator_duplicate_groups,
)


def test_detects_duplicate_group() -> None:
    base = {
        "opportunity_title": "Same title",
        "publisher_name": "Agency",
        "opportunity_number": "DUP-1",
        "opportunity_source_type": "federal",
    }
    det = detect_operator_duplicate_groups([base, dict(base)])
    assert det["duplicate_collision_count"] == 1
    assert det["requires_operator_approval"] is True


def test_operator_approval_clears_requirement() -> None:
    det = detect_operator_duplicate_groups([{"opportunity_title": "A"}])
    approved = apply_operator_duplicate_approval(
        det, operator_approved=True, operator_note="desk review"
    )
    assert approved["operator_approved_duplicate_resolution"] is True

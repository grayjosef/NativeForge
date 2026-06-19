"""Sprint 210: operator review queue and gate verification."""

from __future__ import annotations

from nativeforge.services.org_applicant_profile_stage7_gate_verification_service import (
    GATE_SCHEMA_VERSION,
    build_operator_review_queue,
    verify_stage7_org_profile_gates_on_demo_corpus,
)


def test_operator_review_queue_populated() -> None:
    queue = build_operator_review_queue()
    assert queue["queue_item_count"] >= 1
    assert queue["requires_operator_action"] is True


def test_stage7_gate_verification_passes() -> None:
    result = verify_stage7_org_profile_gates_on_demo_corpus()
    assert result["schema_version"] == GATE_SCHEMA_VERSION
    assert result["verification_passed"] is True
    assert result["checks"]["verified_by_user_guard_exercised"] is True

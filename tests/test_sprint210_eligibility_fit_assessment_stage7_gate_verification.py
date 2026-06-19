"""Sprint 210: operator review queue and Stage 7 gate verification."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_demo_fixture_service import (
    load_opportunity_fixtures,
)
from nativeforge.services.eligibility_fit_assessment_stage7_gate_verification_service import (
    GATE_SCHEMA_VERSION,
    build_operator_review_queue,
    verify_stage7_gates_on_demo_corpus,
)


def test_operator_review_queue_populated() -> None:
    queue = build_operator_review_queue(load_opportunity_fixtures())
    assert queue["queue_item_count"] >= 1
    assert queue["requires_operator_action"] is True


def test_stage7_verification_passes() -> None:
    result = verify_stage7_gates_on_demo_corpus()
    assert result["schema_version"] == GATE_SCHEMA_VERSION
    assert result["verification_passed"] is True
    assert result["checks"]["claim_guard_exercised"] is True
    assert result["checks"]["discoverability_guard_exercised"] is True

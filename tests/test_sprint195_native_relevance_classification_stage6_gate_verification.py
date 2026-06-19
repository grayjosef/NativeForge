"""Sprint 195: Stage 6 gate verification."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_stage6_gate_verification_service import (
    SCHEMA_VERSION,
    verify_stage6_gates_on_demo_corpus,
)


def test_stage6_verification_passes_on_demo_corpus() -> None:
    result = verify_stage6_gates_on_demo_corpus()
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["verification_passed"] is True
    assert result["checks"]["overclaim_guard_exercised"] is True

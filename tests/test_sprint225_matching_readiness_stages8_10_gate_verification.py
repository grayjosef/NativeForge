"""Sprint 225: Stages 8-10 gate verification."""

from __future__ import annotations

from nativeforge.services.matching_readiness_stages8_10_gate_verification_service import (
    SCHEMA_VERSION,
    verify_stages8_10_gates_on_demo_corpus,
)


def test_gate_verification_passes() -> None:
    result = verify_stages8_10_gates_on_demo_corpus()
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["verification_passed"] is True
    assert result["checks"]["canonical_eligibility_fit_layer_used"] is True
    assert result["reconciliation_cleanup_candidates"] == []
    assert result["reconciliation_status"]["operator_next_check"]

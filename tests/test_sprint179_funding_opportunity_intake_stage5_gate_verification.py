"""Sprint 179: Stage 5 gate verification."""

from __future__ import annotations

from nativeforge.services.funding_opportunity_intake_stage5_gate_verification_service import (
    verify_stage5_gates_on_demo_corpus,
)


def test_gate_verification_runs_on_demo_corpus() -> None:
    out = verify_stage5_gates_on_demo_corpus()
    assert out["fixture_count"] >= 2
    assert out["synthetic_only"] is True

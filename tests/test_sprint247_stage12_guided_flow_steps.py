"""Sprint 247: guided flow step vocabulary."""

from __future__ import annotations

from nativeforge.services.stage12_guided_flow_step_vocabulary_service import (
    GUIDED_FLOW_STEPS,
    build_guided_flow_step_contract,
    step_index,
)


def test_eight_guided_steps() -> None:
    assert len(GUIDED_FLOW_STEPS) == 8
    assert GUIDED_FLOW_STEPS[0] == "source-discovery"
    assert GUIDED_FLOW_STEPS[-1] == "evidence-audit-trail"


def test_step_index() -> None:
    assert step_index("operator-decision") == 6


def test_step_contract() -> None:
    contract = build_guided_flow_step_contract()
    assert len(contract["steps"]) == 8

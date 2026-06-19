"""Sprint 211: Stage 7 closeout packet."""

from __future__ import annotations

import json

from nativeforge.services.eligibility_fit_assessment_stage7_closeout_packet_service import (
    ARTIFACT_TYPE,
    build_eligibility_fit_assessment_stage7_closeout_packet,
    render_eligibility_fit_assessment_stage7_closeout_packet_markdown,
)


def test_closeout_packet_shape() -> None:
    packet = build_eligibility_fit_assessment_stage7_closeout_packet()
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["gate_verification_passed"] is True
    assert len(packet["hard_invariants"]) == 2
    json.dumps(packet)


def test_closeout_markdown_renders() -> None:
    md = render_eligibility_fit_assessment_stage7_closeout_packet_markdown()
    assert "Stage 7 Closeout" in md
    assert "eligibility claim" in md

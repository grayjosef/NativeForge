"""Sprint 226: Stages 8-10 closeout packet."""

from __future__ import annotations

import json

from nativeforge.services.matching_readiness_stages8_10_closeout_packet_service import (
    ARTIFACT_TYPE,
    build_matching_readiness_stages8_10_closeout_packet,
    render_matching_readiness_stages8_10_closeout_packet_markdown,
)


def test_closeout_packet_shape() -> None:
    packet = build_matching_readiness_stages8_10_closeout_packet()
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["gate_verification_passed"] is True
    assert len(packet["hard_invariants"]) == 4
    assert packet["canonical_fit_layer"] == "eligibility_fit_assessment_*"
    json.dumps(packet)


def test_closeout_markdown_renders() -> None:
    md = render_matching_readiness_stages8_10_closeout_packet_markdown()
    assert "Stages 8-10 Closeout" in md
    assert "reconciliation" in md.lower() or "Reconciliation" in md

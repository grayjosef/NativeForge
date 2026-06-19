"""Sprint 256: Stage 12 closeout packet."""

from __future__ import annotations

import json

from nativeforge.services.stage12_guided_demo_closeout_packet_service import (
    ARTIFACT_TYPE,
    GUIDED_FLOW_STEPS,
    build_stage12_guided_demo_closeout_packet,
)


def test_closeout_packet_shape() -> None:
    smoke = [{"step": s, "pass": True} for s in GUIDED_FLOW_STEPS]
    packet = build_stage12_guided_demo_closeout_packet(smoke_results=smoke)
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["smoke_verification_passed"] is True
    assert len(packet["guided_flow_steps"]) == 8
    json.dumps(packet)

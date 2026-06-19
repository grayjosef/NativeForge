"""Sprint 241: Stage 11 closeout packet."""

from __future__ import annotations

import json

from nativeforge.services.operator_workbench_stage11_closeout_packet_service import (
    ARTIFACT_TYPE,
    WORKBENCH_SCREENS,
    build_operator_workbench_stage11_closeout_packet,
)


def test_closeout_packet_shape() -> None:
    smoke = [{"screen": s, "pass": True} for s in WORKBENCH_SCREENS]
    packet = build_operator_workbench_stage11_closeout_packet(smoke_results=smoke)
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["smoke_verification_passed"] is True
    assert len(packet["stage11_screens"]) == 6
    json.dumps(packet)


def test_closeout_fails_smoke_when_any_screen_fails() -> None:
    packet = build_operator_workbench_stage11_closeout_packet(
        smoke_results=[{"screen": "x", "pass": False}],
    )
    assert packet["smoke_verification_passed"] is False

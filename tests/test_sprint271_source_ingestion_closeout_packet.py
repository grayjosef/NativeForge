"""Sprint 271: closeout packet."""

from __future__ import annotations

import json

from nativeforge.services.source_ingestion_closeout_packet_service import (
    ARTIFACT_TYPE,
    build_source_ingestion_closeout_packet,
)
from nativeforge.services.source_ingestion_gate_verification_service import (
    verify_source_ingestion_gates,
)


def test_closeout_packet() -> None:
    gate = verify_source_ingestion_gates()
    packet = build_source_ingestion_closeout_packet(gate_verification=gate)
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["gate_verification_passed"] is True
    json.dumps(packet)

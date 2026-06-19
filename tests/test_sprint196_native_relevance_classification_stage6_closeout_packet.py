"""Sprint 196: Stage 6 closeout packet."""

from __future__ import annotations

import json

from nativeforge.services.native_relevance_classification_stage6_closeout_packet_service import (
    ARTIFACT_TYPE,
    build_native_relevance_classification_stage6_closeout_packet,
    render_native_relevance_classification_stage6_closeout_packet_markdown,
)


def test_closeout_packet_shape() -> None:
    packet = build_native_relevance_classification_stage6_closeout_packet()
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["gate_verification_passed"] is True
    assert len(packet["classification_labels"]) == 8
    assert len(packet["hard_invariants"]) == 2
    json.dumps(packet)


def test_closeout_markdown_renders() -> None:
    md = render_native_relevance_classification_stage6_closeout_packet_markdown()
    assert "Stage 6 Closeout" in md
    assert "overclaim guard" in md

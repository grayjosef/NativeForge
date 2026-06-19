"""Sprint 211: Stage 7 org/applicant profile closeout packet."""

from __future__ import annotations

import json

from nativeforge.services.org_applicant_profile_stage7_closeout_packet_service import (
    ARTIFACT_TYPE,
    build_org_applicant_profile_stage7_closeout_packet,
    render_org_applicant_profile_stage7_closeout_packet_markdown,
)


def test_closeout_packet_shape() -> None:
    packet = build_org_applicant_profile_stage7_closeout_packet()
    assert packet["artifact_type"] == ARTIFACT_TYPE
    assert packet["gate_verification_passed"] is True
    assert len(packet["hard_invariants"]) == 3
    assert len(packet["profile_schema_fields"]) == 20
    json.dumps(packet)


def test_closeout_markdown_renders() -> None:
    md = render_org_applicant_profile_stage7_closeout_packet_markdown()
    assert "Stage 7 Closeout" in md
    assert "verified_by_user" in md

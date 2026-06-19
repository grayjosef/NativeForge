"""Sprint 181: Stage 5 closeout packet."""

from __future__ import annotations

import json

from nativeforge.services.funding_opportunity_intake_stage5_closeout_packet_service import (
    build_funding_opportunity_intake_stage5_closeout_packet,
    render_funding_opportunity_intake_stage5_closeout_packet_markdown,
)


def test_closeout_packet() -> None:
    pkt = build_funding_opportunity_intake_stage5_closeout_packet()
    assert pkt["sprint_number"] == 181
    assert pkt["preview_only"] is True
    assert pkt["synthetic_fixtures_only"] is True
    for key, val in pkt.items():
        if key.startswith("actual_"):
            assert val == 0


def test_closeout_markdown() -> None:
    md = render_funding_opportunity_intake_stage5_closeout_packet_markdown()
    assert "Stage 5 Closeout" in md
    assert "Fail-Closed" in md


def test_deterministic() -> None:
    a = build_funding_opportunity_intake_stage5_closeout_packet()
    b = build_funding_opportunity_intake_stage5_closeout_packet()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

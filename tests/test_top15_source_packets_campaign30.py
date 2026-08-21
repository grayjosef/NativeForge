"""Tests: Campaign Block 30 Top-15 source packets."""

from __future__ import annotations

from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.state_source_packet_service import (
    build_state_source_packet,
    resolve_coverage_confidence,
    state_source_packet_invariant_failures,
)
from nativeforge.services.top15_source_validation_assembler_service import (
    build_top15_source_validation_demo_surface,
    top15_source_validation_demo_surface_invariant_failures,
)


def test_live_coverage_requires_check_run() -> None:
    pkt = build_state_source_packet(
        state_code="OK",
        state_name="Oklahoma",
        source_status="identified",
        validation_status="validated_for_demo",
        live_check_supported=True,
        live_check_run=False,
    )
    assert pkt["coverage_live_claimed"] is False
    assert state_source_packet_invariant_failures(pkt) == []
    res = resolve_coverage_confidence(pkt)
    assert res["coverage_live_claimed"] is False


def test_all_top15_packeted() -> None:
    surface = build_top15_source_validation_demo_surface()
    assert top15_source_validation_demo_surface_invariant_failures(surface) == []
    assert surface["packet_count"] == 15
    assert surface["all_top15_live_claimed"] is False
    assert surface["non_sc_live_coverage_claimed"] is False
    assert surface["active_customer_lane"] == "SC"


def test_bridge() -> None:
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["top15_source_validation"]["packet_count"] == 15
    assert payload["top15_source_validation"]["all_top15_live_claimed"] is False

"""Tests: Campaign Block 26 external pilot / pen-test readiness."""

from __future__ import annotations

from nativeforge.services.external_pilot_auth_spike_service import (
    build_external_pilot_auth_spike,
    external_pilot_auth_spike_invariant_failures,
)
from nativeforge.services.gate10_closeout_assembler_service import (
    build_gate10_closeout_demo_surface,
    gate10_closeout_demo_surface_invariant_failures,
)
from nativeforge.services.pen_test_sca_readiness_packet_service import (
    build_pen_test_sca_readiness_packet,
    pen_test_sca_packet_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_external_pilot_login_not_live() -> None:
    spike = build_external_pilot_auth_spike()
    assert spike["login_live_claimed"] is False
    assert spike["production_auth_claimed"] is False
    assert spike["controlled_customer_pilot_status"] == "NO_GO"
    assert external_pilot_auth_spike_invariant_failures(spike) == []


def test_pen_test_not_passed() -> None:
    packet = build_pen_test_sca_readiness_packet(run_sca=False)
    assert packet["pen_test_passed_claimed"] is False
    assert packet["pen_test_readiness_complete"] is True
    assert packet["sca_readiness_complete"] is True
    assert packet["sca_passed_claimed"] is False
    assert pen_test_sca_packet_invariant_failures(packet) == []


def test_gate10_closeout_and_bridge() -> None:
    surface = build_gate10_closeout_demo_surface()
    assert gate10_closeout_demo_surface_invariant_failures(surface) == []
    assert surface["monday_demo_status"] == "GO"
    assert surface["controlled_customer_pilot_status"] == "NO_GO"
    assert surface["production_rollout_status"] == "NO_GO"
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["gate10_closeout"]["login_live_claimed"] is False
    assert payload["gate10_closeout"]["pen_test_passed_claimed"] is False

"""Tests: Campaign Block 74 launch packet."""

from nativeforge.services.gate32_launch_packet_assembler_service import (
    build_launch_packet_demo_surface,
    launch_packet_demo_surface_invariant_failures,
)
from nativeforge.services.gate32_launch_packet_service import build_launch_packet
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_launch_packet_gates() -> None:
    pkt = build_launch_packet()
    assert pkt["owner_gated_blockers"]
    assert pkt["non_owner_blockers"]
    assert pkt["controlled_customer_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    review = build_launch_packet(ready_for_owner_review=True)
    assert review["launch_status"] != "controlled_customer_go"
    assert review["controlled_customer_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    assert "login_live" in review["forbidden_claims"]
    assert review["next_action_sequence"]
    still = build_launch_packet(
        login_live=False,
        production_auth=False,
        production_storage=False,
        pen_test_passed=False,
    )
    assert still["controlled_customer_pilot_status"] == "CONDITIONAL_INTERNAL_ONLY"


def test_demo_bridge() -> None:
    surface = build_launch_packet_demo_surface()
    assert launch_packet_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["launch_packet"]["production_rollout_status"] == (
        "PRODUCTION_ROLLOUT_NO_GO"
    )

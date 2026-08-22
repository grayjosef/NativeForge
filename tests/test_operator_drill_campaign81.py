"""Tests: Campaign Block 81 operator drills."""

from nativeforge.services.gate34_operator_drill_assembler_service import (
    build_operator_drill_demo_surface,
    operator_drill_demo_surface_invariant_failures,
)
from nativeforge.services.gate34_operator_drill_service import (
    run_one_drill,
    run_operator_drills,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_drill_gates() -> None:
    bundle = run_operator_drills()
    assert bundle["pilot_go_claimed"] is False
    assert bundle["production_rollout_claimed"] is False
    assert bundle["owner_input_still_blocker"] is True
    assert bundle["alert_sent_claimed"] is False
    restore = run_one_drill(
        "restore_rehearsal_runbook", evidence_ref="nf://drill/restore"
    )
    assert restore["production_restore_claimed"] is False
    assert restore["status"] == "drill_passed"
    missing = run_one_drill("demo_route_runbook", want_pass=True, evidence_ref=None)
    assert missing["status"] == "drill_failed"
    blocked = run_one_drill("launch_packet_runbook", blocked_owner=True)
    assert blocked["status"] == "blocked_missing_owner_input"


def test_demo_bridge() -> None:
    surface = build_operator_drill_demo_surface()
    assert operator_drill_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["operator_drill"]["pilot_go_claimed"] is False

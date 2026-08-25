"""Tests: Campaign Block 65 final GO/NO-GO closeout."""

from __future__ import annotations

from nativeforge.services.gate26_controlled_pilot_master_service import (
    STATUS_CONDITIONAL_INTERNAL,
    STATUS_CONTROLLED_GO,
    STATUS_PROD_ROLLOUT_NO_GO,
    STATUS_READY_LIMITED_EXT,
)
from nativeforge.services.gate30_final_closeout_assembler_service import (
    build_final_closeout_demo_surface,
    final_closeout_demo_surface_invariant_failures,
)
from nativeforge.services.gate30_final_closeout_service import (
    final_closeout_invariant_failures,
    resolve_final_pilot_packet,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def _assert_not_go(packet: dict) -> None:
    assert packet["controlled_customer_pilot_status"] != STATUS_CONTROLLED_GO
    assert packet["production_rollout_status"] == STATUS_PROD_ROLLOUT_NO_GO


def test_hard_gates_block_customer_go() -> None:
    for kwargs in (
        {
            "login_live": False,
            "production_auth": True,
            "production_storage": True,
            "customer_persistence": True,
            "pen_test_passed": True,
        },
        {
            "login_live": True,
            "production_auth": False,
            "production_storage": True,
            "customer_persistence": True,
            "pen_test_passed": True,
        },
        {
            "login_live": True,
            "production_auth": True,
            "production_storage": False,
            "customer_persistence": True,
            "pen_test_passed": True,
        },
        {
            "login_live": True,
            "production_auth": True,
            "production_storage": True,
            "customer_persistence": False,
            "pen_test_passed": True,
        },
        {
            "login_live": True,
            "production_auth": True,
            "production_storage": True,
            "customer_persistence": True,
            "pen_test_passed": False,
        },
    ):
        packet = resolve_final_pilot_packet(**kwargs)
        _assert_not_go(packet)
        assert packet["blocks_go"]


def test_limited_external_policy_exception() -> None:
    packet = resolve_final_pilot_packet(
        login_live=True,
        production_auth=True,
        production_storage=True,
        customer_persistence=True,
        pen_test_passed=False,
        allow_limited_external_without_pentest=True,
    )
    assert packet["controlled_customer_pilot_status"] == STATUS_READY_LIMITED_EXT
    assert packet["production_rollout_status"] == STATUS_PROD_ROLLOUT_NO_GO


def test_authority_and_coverage_forbidden_claims() -> None:
    packet = resolve_final_pilot_packet()
    forbidden = {x["claim"] for x in packet["forbidden_claims_with_reason"]}
    assert "final_eligibility" in forbidden
    assert "submission_ready" in forbidden
    assert "broad_coverage" in forbidden
    for item in packet["forbidden_claims_with_reason"]:
        assert item["reason"] or item["missing_evidence"]
    for item in packet["allowed_claims_with_evidence"]:
        assert item["evidence"]


def test_mode_a_demo_and_bridge() -> None:
    surface = build_final_closeout_demo_surface()
    assert final_closeout_demo_surface_invariant_failures(surface) == []
    assert final_closeout_invariant_failures(surface["result"]) == []
    assert surface["controlled_customer_pilot_status"] == STATUS_CONDITIONAL_INTERNAL
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["final_closeout"]["fake_production_ready"] is False
    assert payload["final_closeout"]["fake_pilot_ready"] is False

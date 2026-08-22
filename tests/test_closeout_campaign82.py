"""Tests: Campaign Block 82 pre-owner closeout."""

from nativeforge.services.gate34_closeout_assembler_service import (
    build_closeout_demo_surface,
    closeout_demo_surface_invariant_failures,
)
from nativeforge.services.gate34_closeout_service import build_pre_owner_closeout
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_closeout_gates() -> None:
    pkt = build_pre_owner_closeout()
    assert "auth0_oidc_config" in pkt["owner_input_package_checklist"]
    assert "storage_approval_token" in pkt["owner_input_package_checklist"]
    assert pkt["controlled_customer_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    vendor = build_pre_owner_closeout(
        login_live=True, production_storage=True, pen_test_passed=False
    )
    assert vendor["missing_vendor_inputs"]
    assert vendor["controlled_customer_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    assert "production-ready" in pkt["forbidden_claims"]
    seq = " ".join(pkt["post_owner_validator_sequence"])
    assert "auth" in seq and "storage" in seq and "pen-test" in seq
    assert "pilot resolver" in seq
    assert pkt["production_rollout_status"] == "PRODUCTION_ROLLOUT_NO_GO"


def test_demo_bridge() -> None:
    surface = build_closeout_demo_surface()
    assert closeout_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["pre_owner_closeout"]["production_rollout_status"] == (
        "PRODUCTION_ROLLOUT_NO_GO"
    )

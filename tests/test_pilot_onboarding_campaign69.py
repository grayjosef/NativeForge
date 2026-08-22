"""Tests: Campaign Block 69 pilot onboarding."""

from nativeforge.services.gate31_pilot_onboarding_assembler_service import (
    build_pilot_onboarding_demo_surface,
    pilot_onboarding_demo_surface_invariant_failures,
)
from nativeforge.services.gate31_pilot_onboarding_service import (
    BLOCKED_ROUTES,
    resolve_invite_readiness,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_gates_block_invite_and_access() -> None:
    login = resolve_invite_readiness(login_live=False, production_auth=True)
    assert login["invite_send_gate"] is False
    auth = resolve_invite_readiness(login_live=True, production_auth=False)
    assert auth["invite_send_gate"] is False
    storage = resolve_invite_readiness(
        login_live=True,
        production_auth=True,
        storage_ready=False,
        persistence_required=True,
    )
    assert "storage_ready" in storage["missing_gates"]
    pentest = resolve_invite_readiness(
        login_live=True,
        production_auth=True,
        storage_ready=True,
        pen_test_ready=False,
        limited_validation_policy=False,
    )
    assert "pen_test_ready" in pentest["missing_gates"]
    approval = resolve_invite_readiness(operator_approval=False)
    assert "operator_approval" in approval["missing_gates"]
    role = resolve_invite_readiness(role="customer")
    assert role["customer_can_access_operator_surfaces"] is False
    assert "/submit" in BLOCKED_ROUTES
    freeze = resolve_invite_readiness(
        login_live=True,
        production_auth=True,
        storage_ready=True,
        customer_data_policy_ready=True,
        pen_test_ready=True,
        support_ready=True,
        operator_approval=True,
        claim_freeze_verified=False,
    )
    assert freeze["invite_send_gate"] is False


def test_demo_bridge() -> None:
    surface = build_pilot_onboarding_demo_surface()
    assert pilot_onboarding_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["pilot_org_onboarding"]["invite_sent_claimed"] is False
    assert payload["pilot_org_onboarding"]["customer_access_claim"] is False

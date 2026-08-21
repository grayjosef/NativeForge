"""Tests: Campaign Block 37 external pilot auth path."""

from __future__ import annotations

from nativeforge.services.auth_provider_decision_matrix_service import (
    auth_provider_decision_matrix_invariant_failures,
    build_auth_provider_decision_matrix,
)
from nativeforge.services.external_auth_context_adapter_service import (
    adapt_external_auth_context,
    external_auth_adapter_invariant_failures,
)
from nativeforge.services.external_pilot_auth_assembler_service import (
    build_external_pilot_auth_demo_surface,
    external_pilot_auth_demo_surface_invariant_failures,
)
from nativeforge.services.pilot_invite_allowlist_contract_service import (
    build_pilot_invite_contract,
    pilot_invite_contract_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_auth_matrix_recommends_oidc() -> None:
    m = build_auth_provider_decision_matrix()
    assert m["recommended_provider_id"] == "auth0_oidc"
    assert m["login_live_claimed"] is False
    assert auth_provider_decision_matrix_invariant_failures(m) == []


def test_invite_default_not_sent() -> None:
    inv = build_pilot_invite_contract(
        organization_profile_id="org1",
        invitee_email="a@example.com",
        invite_status="sent",  # attempt send without deps
    )
    assert inv["invite_status"] != "sent"
    assert inv["pilot_go_claimed"] is False
    assert pilot_invite_contract_invariant_failures(inv) == []


def test_missing_provider_cannot_claim_live_login() -> None:
    ctx = adapt_external_auth_context(email="a@example.com")
    assert ctx["external_auth_configured"] is False
    assert ctx["login_live_claimed"] is False
    assert ctx["fallback_auth_mode"] == "fixture_internal"
    assert external_auth_adapter_invariant_failures(ctx) == []


def test_demo_and_bridge() -> None:
    surface = build_external_pilot_auth_demo_surface()
    assert external_pilot_auth_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["external_pilot_auth"]["login_live_claimed"] is False
    assert payload["external_pilot_auth"]["controlled_customer_pilot_status"] == (
        "NO_GO"
    )

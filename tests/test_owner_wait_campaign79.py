"""Tests: Campaign Block 79 owner wait-state."""

from nativeforge.services.gate34_owner_wait_assembler_service import (
    build_owner_wait_demo_surface,
    owner_wait_demo_surface_invariant_failures,
)
from nativeforge.services.gate34_owner_wait_service import (
    resolve_category,
    resolve_owner_wait_state,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_owner_wait_gates() -> None:
    auth = resolve_category("auth0_oidc_config", value=None)
    assert auth["wait_state"] == "blocked_owner_input"
    storage = resolve_category("storage_approval_token", value=None)
    assert storage["wait_state"] == "blocked_owner_input"
    pen = resolve_category("pen_test_report", value=None)
    assert pen["wait_state"] == "blocked_external_vendor"
    synth = resolve_category("auth0_oidc_config", value="synthetic")
    assert synth["satisfied"] is False
    prompt = resolve_category("storage_approval_token", value="prompt")
    assert prompt["satisfied"] is False
    unval = resolve_category("auth0_oidc_config", value="present_unvalidated")
    assert unval["status"] == "required_present_unvalidated"
    bundle = resolve_owner_wait_state(
        inputs={"auth0_oidc_config": "present_unvalidated"}
    )
    assert bundle["live_claims_unlocked"] is False
    assert "auth0_oidc_config" in bundle["final_resolver_blockers"] or (
        "auth0_oidc_config" in bundle["present_unvalidated_inputs"]
    )
    default = resolve_owner_wait_state()
    assert "auth0_oidc_config" in default["final_resolver_blockers"]


def test_demo_bridge() -> None:
    surface = build_owner_wait_demo_surface()
    assert owner_wait_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["owner_wait"]["no_progress_without_input"] is True

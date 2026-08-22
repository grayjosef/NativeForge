"""Tests: Campaign Block 86 post-input pilot resolver."""

from nativeforge.services.gate35_ingest_assembler_service import (
    build_pilot_resolver_demo_surface,
    pilot_resolver_demo_surface_invariant_failures,
)
from nativeforge.services.gate35_pilot_resolver_service import resolve_post_input_pilot
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def _all_hard(**extra: bool) -> dict[str, bool]:
    base = {
        "login_live": True,
        "production_auth": True,
        "production_storage": True,
        "customer_persistence": True,
        "customer_data_policy_ready": True,
        "tenant_boundary_validated": True,
        "audit_validated": True,
        "pen_test_passed": True,
        "support_owner_assigned": True,
        "incident_escalation_owner_assigned": True,
        "invite_readiness": True,
        "operator_approval": True,
        "claim_freeze_verified": True,
    }
    base.update(extra)
    return base


def test_pilot_resolver_gates() -> None:
    missing = resolve_post_input_pilot()
    assert missing["controlled_customer_pilot_status"] == "CONDITIONAL_INTERNAL_ONLY"
    auth_only = resolve_post_input_pilot(login_live=True, production_auth=True)
    assert auth_only["controlled_customer_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    stor_only = resolve_post_input_pilot(production_storage=True)
    assert stor_only["controlled_customer_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    pt_only = resolve_post_input_pilot(pen_test_passed=True)
    assert pt_only["controlled_customer_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    go = resolve_post_input_pilot(**_all_hard())
    assert go["controlled_customer_pilot_status"] == "CONTROLLED_CUSTOMER_GO"
    assert go["production_rollout_status"] == "PRODUCTION_ROLLOUT_NO_GO"
    freeze = resolve_post_input_pilot(**_all_hard(claim_freeze_verified=False))
    assert freeze["controlled_customer_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    assert "production-ready" in missing["forbidden_claims"]


def test_demo_bridge() -> None:
    surface = build_pilot_resolver_demo_surface()
    assert pilot_resolver_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["pilot_resolver"]["controlled_customer_pilot_status"] != (
        "CONTROLLED_CUSTOMER_GO"
    )

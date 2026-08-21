"""Tests: Campaign Block 35 RBAC enforcement."""

from __future__ import annotations

from nativeforge.services.auth_context_resolver_service import (
    auth_context_resolver_invariant_failures,
    resolve_auth_context,
)
from nativeforge.services.rbac_enforcement_assembler_service import (
    build_rbac_enforcement_demo_surface,
    rbac_enforcement_demo_surface_invariant_failures,
)
from nativeforge.services.rbac_enforcement_service import (
    enforce_rbac_access,
    run_rbac_enforcement_suite,
)
from nativeforge.services.rbac_policy_contract_service import (
    build_rbac_policy_contract,
    rbac_policy_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_sensitive_actions_denied_by_default() -> None:
    for role in ("viewer", "tribal_admin", "operator_admin", "unknown"):
        p = build_rbac_policy_contract(
            user_id="u1", organization_profile_id="org1", role=role
        )
        assert "submit" not in p["allowed_actions"]
        assert "final_export" not in p["allowed_actions"]
        assert "manage_users" not in p["allowed_actions"]
        assert rbac_policy_invariant_failures(p) == []


def test_unknown_and_missing_org_deny() -> None:
    ctx = resolve_auth_context(
        organization_profile_id=None, role="grant_manager", context_kind="customer"
    )
    assert ctx["role"] == "unknown"
    assert ctx["login_live_claimed"] is False
    assert auth_context_resolver_invariant_failures(ctx) == []

    r = enforce_rbac_access(
        action="view",
        object_type="evidence_intake",
        object_id="e1",
        resource_org_id="org_a",
        organization_profile_id="",
        role="viewer",
    )
    assert r["allowed"] is False
    assert r["denial_audit_event"] is not None


def test_customer_cannot_use_operator_role() -> None:
    ctx = resolve_auth_context(
        role="operator_admin", context_kind="customer", organization_profile_id="org1"
    )
    assert ctx["role"] == "unknown"


def test_enforcement_suite_and_bridge() -> None:
    suite = run_rbac_enforcement_suite()
    assert suite["overall_status"] == "PASS"
    surface = build_rbac_enforcement_demo_surface()
    assert rbac_enforcement_demo_surface_invariant_failures(surface) == []
    assert surface["login_live_claimed"] is False
    assert surface["rbac_enforced_claimed"] is True
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["rbac_enforcement"]["controlled_customer_pilot_status"] == "NO_GO"

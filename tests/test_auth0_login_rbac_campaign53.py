"""Tests: Campaign Block 53 Auth0 login / RBAC validation."""

from __future__ import annotations

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
)
from nativeforge.services.auth0_login_rbac_validation_assembler_service import (
    auth0_login_rbac_demo_surface_invariant_failures,
    build_auth0_login_rbac_demo_surface,
)
from nativeforge.services.auth0_login_rbac_validation_service import (
    auth0_login_rbac_validation_invariant_failures,
    resolve_controlled_pilot_auth_readiness,
    resolve_production_auth_claim,
    run_auth0_login_rbac_validation,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_mode_a_and_secret_cannot_unlock_login() -> None:
    collector = AuditEventCollector()
    result = run_auth0_login_rbac_validation(
        role_for_sensitive_check="unknown", collector=collector
    )
    assert result["mode"] == "A"
    assert result["login_live_claimed"] is False
    assert result["production_auth_claimed"] is False
    assert result["live_validation_attempted"] is False
    # secret_present may be true or false from env — alone must not unlock
    assert result["login_live_claimed"] is False
    assert result["rbac_sensitive_denied"] is True
    assert collector.has_event("rbac_deny")
    assert auth0_login_rbac_validation_invariant_failures(result) == []


def test_missing_invite_org_blocks_pilot_auth() -> None:
    result = run_auth0_login_rbac_validation(
        invite_binding_passed=False,
        org_binding_passed=False,
    )
    pilot = resolve_controlled_pilot_auth_readiness(result)
    assert pilot["controlled_pilot_auth_ready"] is False
    prod = resolve_production_auth_claim(result)
    assert prod["production_auth_claimed"] is False
    assert (
        "invite_binding" in result["missing_gates"]
        or "invite_allowlist" in result["missing_gates"]
    )


def test_tenant_boundary_failure_blocks() -> None:
    result = run_auth0_login_rbac_validation(tenant_boundary_passed=False)
    assert result["controlled_pilot_auth_ready"] is False
    assert result["login_live_claimed"] is False
    assert "tenant_boundary" in result["missing_gates"]


def test_demo_and_bridge() -> None:
    surface = build_auth0_login_rbac_demo_surface()
    assert auth0_login_rbac_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["auth0_login_rbac"]["login_live_claimed"] is False
    assert payload["auth0_login_rbac"]["fake_login_ui"] is False

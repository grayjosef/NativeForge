"""Pilot org onboarding + invite readiness workflow (Block 69)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
    new_collector,
)

SCHEMA_VERSION = "nf_gate31_pilot_onboarding_v1"

ORG_STATUSES = (
    "not_started",
    "draft",
    "needs_owner_review",
    "blocked_auth",
    "blocked_storage",
    "blocked_security",
    "blocked_policy",
    "blocked_authority",
    "blocked_source_coverage",
    "ready_for_internal_review",
    "ready_for_limited_external_validation",
    "ready_for_invite_send",
    "invite_sent",
    "active_controlled_pilot",
    "blocked",
    "unknown",
)

ALLOWED_ROUTES = ("/?view=sc_customer_demo",)
BLOCKED_ROUTES = (
    "/submit",
    "/final-export",
    "/operator",
    "/collaboration-match",
)

def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_invite_readiness(
    *,
    login_live: bool = False,
    production_auth: bool = False,
    rbac_ready: bool = True,
    tenant_ready: bool = True,
    storage_ready: bool = False,
    persistence_required: bool = True,
    customer_data_policy_ready: bool = False,
    pen_test_ready: bool = False,
    limited_validation_policy: bool = False,
    support_ready: bool = False,
    operator_approval: bool = False,
    claim_freeze_verified: bool = True,
    role: str = "customer",
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    missing: list[str] = []
    if not login_live:
        missing.append("auth_ready")
    if not production_auth:
        missing.append("production_auth")
    if not rbac_ready:
        missing.append("rbac_ready")
    if not tenant_ready:
        missing.append("tenant_ready")
    if persistence_required and not storage_ready:
        missing.append("storage_ready")
    if not customer_data_policy_ready:
        missing.append("customer_data_policy_ready")
    if not pen_test_ready and not limited_validation_policy:
        missing.append("pen_test_ready")
    if not support_ready:
        missing.append("support_ready")
    if not operator_approval:
        missing.append("operator_approval")
    if not claim_freeze_verified:
        missing.append("claim_freeze")

    invite_ok = len(missing) == 0
    # Claim freeze cannot be overridden
    if not claim_freeze_verified:
        invite_ok = False
    if not login_live:
        invite_ok = False
    if not production_auth:
        invite_ok = False

    status = "draft"
    if not login_live or not production_auth:
        status = "blocked_auth"
    elif persistence_required and not storage_ready:
        status = "blocked_storage"
    elif not pen_test_ready and not limited_validation_policy:
        status = "blocked_security"
    elif not customer_data_policy_ready:
        status = "blocked_policy"
    elif invite_ok:
        status = "ready_for_invite_send"
    else:
        status = "needs_owner_review"

    customer_cannot_operator = role != "operator"
    collector.add({"event": "pilot_onboarding_resolve", "invite_ok": invite_ok})

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "pilot_org_onboarding_contract": True,
            "pilot_org_readiness_profile": True,
            "invite_readiness_resolver": True,
            "invite_send_gate": invite_ok,
            "invite_sent_claimed": False,
            "customer_role_model": role,
            "customer_can_access_operator_surfaces": False
            if customer_cannot_operator
            else True,
            "allowed_route_set": list(ALLOWED_ROUTES),
            "blocked_route_set": list(BLOCKED_ROUTES),
            "operator_approval_gate": operator_approval,
            "customer_access_claim": False,
            "customer_active_claimed": False,
            "pilot_org_status": status,
            "org_statuses": list(ORG_STATUSES),
            "missing_gates": missing,
            "claim_freeze_verified": claim_freeze_verified,
            "login_live": login_live,
            "production_auth": production_auth,
        }
    )


def pilot_onboarding_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("invite_sent_claimed") is True:
        fails.append("invite_sent")
    if result.get("customer_access_claim") is True:
        fails.append("customer_access")
    if result.get("customer_active_claimed") is True:
        fails.append("customer_active")
    if result.get("invite_send_gate") and not result.get("login_live"):
        fails.append("invite_without_login")
    if (
        result.get("customer_can_access_operator_surfaces")
        and result.get("customer_role_model") == "customer"
    ):
        fails.append("customer_on_operator")
    return fails

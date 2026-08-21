"""OIDC claims → NativeForge auth context mapper (Block 39)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.auth_context_resolver_service import resolve_auth_context
from nativeforge.services.rbac_enforcement_service import enforce_rbac_access
from nativeforge.services.unified_audit_event_service import build_unified_audit_event

SCHEMA_VERSION = "nf_oidc_identity_mapper_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def map_oidc_claims_to_auth_context(
    *,
    subject: str | None,
    email: str | None = None,
    email_verified: bool = False,
    organization_claim: str | None = None,
    invite_id: str | None = None,
    roles_or_groups: list[str] | None = None,
    allowed_org_binding: str | None = None,
    pilot_cohort_id: str = "cohort_demo",
    provider_validated: bool = False,
    session_status: str = "no_session",
) -> dict[str, Any]:
    # Gate 17: never claim login live in mapper until owner validates provider
    login_live_claimed = False

    reasons: list[str] = []
    if not subject:
        reasons.append("missing_subject")
    if not email:
        reasons.append("missing_email")
    if email and not email_verified:
        reasons.append("email_not_verified")
    if invite_id is None:
        reasons.append("invite_not_bound")
    if (
        allowed_org_binding
        and organization_claim
        and (organization_claim != allowed_org_binding)
    ):
        reasons.append("org_mismatch")
    if not organization_claim and not allowed_org_binding:
        reasons.append("org_binding_missing")

    org_id = allowed_org_binding or organization_claim or ""
    role = "viewer"
    groups = list(roles_or_groups or [])
    if "grant_manager" in groups:
        role = "grant_manager"
    elif "tribal_admin" in groups:
        role = "tribal_admin"
    elif "operator_reviewer" in groups:
        role = "operator_reviewer"

    denied = bool(reasons) or not provider_validated
    auth_ctx = resolve_auth_context(
        user_id=subject or "unknown_oidc_subject",
        organization_profile_id=org_id or None,
        role=role if not denied else "unknown",
        auth_mode="fixture_internal"
        if not provider_validated
        else "external_pilot_configured",
        pilot_cohort_id=pilot_cohort_id,
        context_kind="customer",
    )

    audit = build_unified_audit_event(
        event_type="auth_context_resolved",
        actor_type="system",
        actor_id=subject or "unknown",
        organization_profile_id=org_id or None,
        pilot_cohort_id=pilot_cohort_id,
        object_type="oidc_identity",
        object_id=subject or "missing",
        action="map_claims",
        decision="deny" if denied else "allow_pending_live",
        reason=";".join(reasons) or "mapped_pending_validation",
    )

    # RBAC handoff sample
    rbac = enforce_rbac_access(
        action="view",
        object_type="package_workspace",
        object_id="pkg_demo",
        resource_org_id=org_id or "org_missing",
        auth_context=auth_ctx,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "provider": "auth0_oidc",
            "subject": subject,
            "email": email,
            "email_verified": bool(email_verified),
            "invite_id": invite_id,
            "organization_profile_id": org_id or None,
            "role": auth_ctx.get("role"),
            "session_status": session_status,
            "provider_validated": bool(provider_validated),
            "login_live_claimed": login_live_claimed,
            "mapping_denied": denied,
            "denial_reasons": reasons,
            "auth_context": auth_ctx,
            "rbac_policy_reference": "nf_rbac_policy_contract_v1",
            "tenant_boundary_reference": "nf_tenant_boundary_enforcement_v1",
            "rbac_handoff": rbac,
            "audit_event": audit,
            "allowed_actions": (auth_ctx.get("rbac_policy") or {}).get(
                "allowed_actions"
            ),
            "disallowed_actions": (auth_ctx.get("rbac_policy") or {}).get(
                "disallowed_actions"
            ),
            "production_auth_claimed": False,
            "pilot_go_claimed": False,
        }
    )


def oidc_identity_mapper_invariant_failures(mapped: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in ("login_live_claimed", "production_auth_claimed", "pilot_go_claimed"):
        if mapped.get(key) is True:
            fails.append(key)
    if mapped.get("provider_validated") is False and mapped.get("login_live_claimed"):
        fails.append("live_without_validation")
    return fails

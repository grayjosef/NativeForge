"""RBAC enforcement over core object families (Block 35)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.auth_context_resolver_service import resolve_auth_context
from nativeforge.services.rbac_policy_contract_service import (
    ACTIONS,
    DEFAULT_DISALLOWED,
)
from nativeforge.services.tenant_boundary_enforcement_service import (
    assert_tenant_access,
)

SCHEMA_VERSION = "nf_rbac_enforcement_v1"

OBJECT_FAMILIES = frozenset(
    {
        "org_profile",
        "evidence_intake",
        "evidence_lifecycle",
        "package_workspace",
        "checklist",
        "binder",
        "forms_attachments_map",
        "draft_workspace",
        "controlled_draft",
        "ai_governance",
        "feedback_report",
        "applicant_authority",
        "package_export_preview",
        "source_packet",
        "operator_readiness",
        "collaboration_settings",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _denial_event(
    *,
    reason: str,
    action: str,
    object_type: str,
    object_id: str,
    ctx: dict[str, Any],
    resource_org_id: str,
) -> dict[str, Any]:
    return {
        "audit_event_id": f"aud_{uuid.uuid4().hex[:12]}",
        "event_type": "rbac_deny",
        "actor_type": ctx.get("context_kind") or "unknown",
        "actor_id": ctx.get("user_id"),
        "organization_profile_id": ctx.get("organization_profile_id"),
        "resource_organization_profile_id": resource_org_id,
        "object_type": object_type,
        "object_id": object_id,
        "action": action,
        "decision": "deny",
        "reason": reason,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "sensitive_fields_redacted": True,
        "customer_visible": False,
        "operator_review_required": True,
    }


def enforce_rbac_access(
    *,
    action: str,
    object_type: str,
    object_id: str,
    resource_org_id: str,
    auth_context: dict[str, Any] | None = None,
    user_id: str = "fixture_user_demo",
    organization_profile_id: str = "org_demo_sc",
    role: str = "viewer",
    context_kind: str = "customer",
) -> dict[str, Any]:
    ctx = auth_context or resolve_auth_context(
        user_id=user_id,
        organization_profile_id=organization_profile_id,
        role=role,
        context_kind=context_kind,
    )
    ot = object_type if object_type in OBJECT_FAMILIES else "unknown"
    act = action if action in ACTIONS else "view"
    policy = ctx.get("rbac_policy") or {}
    allowed_actions = set(policy.get("allowed_actions") or [])
    requesting_org = str(ctx.get("organization_profile_id") or "")

    # Hard denies
    if act in DEFAULT_DISALLOWED:
        event = _denial_event(
            reason=f"action_hard_denied:{act}",
            action=act,
            object_type=ot,
            object_id=object_id,
            ctx=ctx,
            resource_org_id=resource_org_id,
        )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "action": act,
                "object_type": ot,
                "object_id": object_id,
                "reason": event["reason"],
                "denial_audit_event": event,
                "rbac_enforced_claimed": True,
                "login_live_claimed": False,
                "production_auth_claimed": False,
            }
        )

    if ot == "collaboration_settings" or act == "manage_collaboration":
        event = _denial_event(
            reason="collaboration_dark_off",
            action=act,
            object_type=ot,
            object_id=object_id,
            ctx=ctx,
            resource_org_id=resource_org_id,
        )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "action": act,
                "object_type": ot,
                "object_id": object_id,
                "reason": event["reason"],
                "denial_audit_event": event,
                "rbac_enforced_claimed": True,
                "login_live_claimed": False,
                "production_auth_claimed": False,
            }
        )

    if not requesting_org:
        event = _denial_event(
            reason="missing_organization_profile",
            action=act,
            object_type=ot,
            object_id=object_id,
            ctx=ctx,
            resource_org_id=resource_org_id,
        )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "action": act,
                "object_type": ot,
                "object_id": object_id,
                "reason": event["reason"],
                "denial_audit_event": event,
                "rbac_enforced_claimed": True,
                "login_live_claimed": False,
                "production_auth_claimed": False,
            }
        )

    tenant = assert_tenant_access(
        requesting_org_id=requesting_org,
        resource_org_id=resource_org_id,
        object_type=ot if ot != "unknown" else "org_profile",
        action=act,
    )
    if not tenant.get("allowed"):
        event = _denial_event(
            reason="cross_org_access_denied",
            action=act,
            object_type=ot,
            object_id=object_id,
            ctx=ctx,
            resource_org_id=resource_org_id,
        )
        event["event_type"] = "cross_org_access_denied"
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "action": act,
                "object_type": ot,
                "object_id": object_id,
                "reason": event["reason"],
                "denial_audit_event": event,
                "rbac_enforced_claimed": True,
                "login_live_claimed": False,
                "production_auth_claimed": False,
            }
        )

    if act not in allowed_actions:
        event = _denial_event(
            reason=f"role_action_denied:{ctx.get('role')}:{act}",
            action=act,
            object_type=ot,
            object_id=object_id,
            ctx=ctx,
            resource_org_id=resource_org_id,
        )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "action": act,
                "object_type": ot,
                "object_id": object_id,
                "reason": event["reason"],
                "denial_audit_event": event,
                "rbac_enforced_claimed": True,
                "login_live_claimed": False,
                "production_auth_claimed": False,
            }
        )

    if ot == "operator_readiness" and ctx.get("context_kind") != "operator":
        event = _denial_event(
            reason="operator_surface_denied_for_customer",
            action=act,
            object_type=ot,
            object_id=object_id,
            ctx=ctx,
            resource_org_id=resource_org_id,
        )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "action": act,
                "object_type": ot,
                "object_id": object_id,
                "reason": event["reason"],
                "denial_audit_event": event,
                "rbac_enforced_claimed": True,
                "login_live_claimed": False,
                "production_auth_claimed": False,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "allowed": True,
            "action": act,
            "object_type": ot,
            "object_id": object_id,
            "reason": "rbac_allow",
            "denial_audit_event": None,
            "allow_audit_event": {
                "event_type": "rbac_allow",
                "actor_id": ctx.get("user_id"),
                "action": act,
                "object_type": ot,
                "object_id": object_id,
                "decision": "allow",
            },
            "rbac_enforced_claimed": True,
            "login_live_claimed": False,
            "production_auth_claimed": False,
        }
    )


def run_rbac_enforcement_suite() -> dict[str, Any]:
    org_a = "org_a_demo"
    org_b = "org_b_demo"
    fails: list[str] = []
    cases = []

    # Same-org viewer can view
    r = enforce_rbac_access(
        action="view",
        object_type="evidence_intake",
        object_id="ev1",
        resource_org_id=org_a,
        organization_profile_id=org_a,
        role="viewer",
    )
    cases.append(("same_org_view", r["allowed"]))
    if not r["allowed"]:
        fails.append("same_org_view")

    # Cross-org deny
    r = enforce_rbac_access(
        action="view",
        object_type="evidence_intake",
        object_id="ev2",
        resource_org_id=org_b,
        organization_profile_id=org_a,
        role="viewer",
    )
    cases.append(("cross_org_deny", not r["allowed"]))
    if r["allowed"] or not r.get("denial_audit_event"):
        fails.append("cross_org_deny")

    # Submit always deny
    r = enforce_rbac_access(
        action="submit",
        object_type="package_workspace",
        object_id="pkg1",
        resource_org_id=org_a,
        organization_profile_id=org_a,
        role="tribal_admin",
    )
    cases.append(("submit_deny", not r["allowed"]))
    if r["allowed"]:
        fails.append("submit_deny")

    # Final export always deny
    r = enforce_rbac_access(
        action="final_export",
        object_type="package_export_preview",
        object_id="exp1",
        resource_org_id=org_a,
        organization_profile_id=org_a,
        role="operator_admin",
        context_kind="operator",
    )
    cases.append(("final_export_deny", not r["allowed"]))
    if r["allowed"]:
        fails.append("final_export_deny")

    # Collaboration deny
    r = enforce_rbac_access(
        action="manage_collaboration",
        object_type="collaboration_settings",
        object_id="collab1",
        resource_org_id=org_a,
        organization_profile_id=org_a,
        role="tribal_admin",
    )
    cases.append(("collab_deny", not r["allowed"]))
    if r["allowed"]:
        fails.append("collab_deny")

    # Manage users deny
    r = enforce_rbac_access(
        action="manage_users",
        object_type="org_profile",
        object_id=org_a,
        resource_org_id=org_a,
        organization_profile_id=org_a,
        role="tribal_admin",
    )
    cases.append(("manage_users_deny", not r["allowed"]))
    if r["allowed"]:
        fails.append("manage_users_deny")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "overall_status": "PASS" if not fails else "FAIL",
            "fails": fails,
            "cases": cases,
            "rbac_enforced_claimed": True,
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "object_families": sorted(OBJECT_FAMILIES),
        }
    )

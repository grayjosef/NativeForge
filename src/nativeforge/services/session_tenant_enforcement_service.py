"""Session + tenant enforcement under live or dry-run auth (Block 54 / Gate 24)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.rbac_enforcement_service import enforce_rbac_access
from nativeforge.services.tenant_boundary_enforcement_service import (
    assert_tenant_access,
)

SCHEMA_VERSION = "nf_session_tenant_enforcement_v1"

SESSION_STATUSES = (
    "not_started",
    "fixture_internal",
    "dry_run",
    "configured_not_validated",
    "live_validated",
    "expired",
    "invalid",
    "blocked",
    "unknown",
)

PROTECTED_OBJECT_FAMILIES = (
    "organization_profile",
    "evidence_intake_lifecycle",
    "customer_data_policy",
    "retention_delete_export",
    "package_workspace",
    "checklist",
    "binder",
    "forms_attachments",
    "draft_workspace",
    "controlled_draft",
    "ai_governance",
    "feedback_reports",
    "applicant_authority",
    "package_export_preview",
    "source_packets",
    "operator_readiness",
    "storage_adapters",
    "audit_trail",
    "collaboration_settings",
)

# Map Gate 24 family names → existing RBAC object types where applicable
_FAMILY_TO_RBAC = {
    "organization_profile": "org_profile",
    "evidence_intake_lifecycle": "evidence_intake",
    "customer_data_policy": "org_profile",
    "retention_delete_export": "package_export_preview",
    "package_workspace": "package_workspace",
    "checklist": "checklist",
    "binder": "binder",
    "forms_attachments": "forms_attachments_map",
    "draft_workspace": "draft_workspace",
    "controlled_draft": "controlled_draft",
    "ai_governance": "ai_governance",
    "feedback_reports": "feedback_report",
    "applicant_authority": "applicant_authority",
    "package_export_preview": "package_export_preview",
    "source_packets": "source_packet",
    "operator_readiness": "operator_readiness",
    "storage_adapters": "operator_readiness",
    "audit_trail": "operator_readiness",
    "collaboration_settings": "collaboration_settings",
}

OPERATOR_ONLY_FAMILIES = frozenset(
    {
        "operator_readiness",
        "storage_adapters",
        "audit_trail",
    }
)

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(event: str, detail: dict[str, Any]) -> None:
    _AUDIT.append(
        {
            "event": event,
            "at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            **detail,
        }
    )


def build_session_context(
    *,
    status: str = "dry_run",
    organization_profile_id: str = "org_a",
    role: str = "customer_user",
    context_kind: str = "customer",
    stale: bool = False,
) -> dict[str, Any]:
    st = status if status in SESSION_STATUSES else "unknown"
    live_access_claimed = False
    if st == "live_validated":
        # Still false unless all Gate 24 auth gates passed externally
        live_access_claimed = False
    if st in {"expired", "invalid", "blocked", "not_started", "unknown"}:
        access_allowed = False
    elif st == "dry_run":
        access_allowed = True  # dry-run fixture access only — not live
        live_access_claimed = False
    elif st == "fixture_internal":
        access_allowed = True
        live_access_claimed = False
    elif st == "configured_not_validated":
        access_allowed = False
    else:
        access_allowed = False

    if stale and st not in {"expired", "invalid"}:
        st = "expired"
        access_allowed = False
        _emit_audit(
            "session_expire", {"organization_profile_id": organization_profile_id}
        )

    _emit_audit(
        "session_resolve",
        {
            "session_status": st,
            "organization_profile_id": organization_profile_id,
            "access_allowed": access_allowed,
        },
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "contract": "session_context",
            "session_status": st,
            "organization_profile_id": organization_profile_id,
            "role": role,
            "context_kind": context_kind,
            "access_allowed": access_allowed,
            "live_access_claimed": live_access_claimed,
            "external_users_can_access_claimed": False,
            "production_multi_tenant_claimed": False,
            "stale": stale or st == "expired",
            "session_statuses": list(SESSION_STATUSES),
        }
    )


def enforce_session_object_access(
    *,
    session: dict[str, Any],
    object_family: str,
    action: str = "view",
    resource_org_id: str,
) -> dict[str, Any]:
    status = session.get("session_status") or "unknown"
    requesting_org = str(session.get("organization_profile_id") or "")
    role = str(session.get("role") or "viewer")
    context_kind = str(session.get("context_kind") or "customer")

    if status in {"expired", "invalid", "blocked", "not_started", "unknown"}:
        _emit_audit(
            "session_deny",
            {
                "reason": f"session_{status}",
                "object_family": object_family,
                "resource_org_id": resource_org_id,
            },
        )
        return _json_safe(
            {
                "allowed": False,
                "reason": f"session_{status}",
                "object_family": object_family,
                "live_access_claimed": False,
                "production_multi_tenant_claimed": False,
            }
        )

    if status == "dry_run" and session.get("live_access_claimed"):
        return _json_safe(
            {
                "allowed": False,
                "reason": "dry_run_cannot_claim_live",
                "object_family": object_family,
                "live_access_claimed": False,
            }
        )

    if object_family in OPERATOR_ONLY_FAMILIES and context_kind != "operator":
        _emit_audit(
            "session_deny",
            {
                "reason": "operator_only_route",
                "object_family": object_family,
                "role": role,
            },
        )
        return _json_safe(
            {
                "allowed": False,
                "reason": "operator_only_route",
                "object_family": object_family,
                "live_access_claimed": False,
            }
        )

    # Cross-org denial
    tenant = assert_tenant_access(
        requesting_org_id=requesting_org,
        resource_org_id=resource_org_id,
        object_type=_FAMILY_TO_RBAC.get(object_family, "org_profile"),
        action=action,
    )
    if not tenant.get("allowed"):
        _emit_audit(
            "cross_org_deny",
            {
                "requesting_org_id": requesting_org,
                "resource_org_id": resource_org_id,
                "object_family": object_family,
            },
        )
        return _json_safe(
            {
                "allowed": False,
                "reason": "cross_org_access_denied",
                "object_family": object_family,
                "denial_audit_event": tenant.get("denial_audit_event"),
                "live_access_claimed": False,
                "production_multi_tenant_claimed": False,
            }
        )

    rbac_ot = _FAMILY_TO_RBAC.get(object_family, "org_profile")
    rbac = enforce_rbac_access(
        action=action
        if action in {"view", "export", "manage_collaboration"}
        else "view",
        object_type=rbac_ot,
        object_id=f"obj_{uuid.uuid4().hex[:8]}",
        resource_org_id=resource_org_id,
        organization_profile_id=requesting_org,
        role="viewer" if role == "customer_user" else role,
        context_kind=context_kind,
    )
    if not rbac.get("allowed"):
        _emit_audit(
            "session_deny",
            {
                "reason": rbac.get("reason"),
                "object_family": object_family,
            },
        )
        return _json_safe(
            {
                "allowed": False,
                "reason": rbac.get("reason"),
                "object_family": object_family,
                "denial_audit_event": rbac.get("denial_audit_event"),
                "live_access_claimed": False,
            }
        )

    _emit_audit(
        "session_allow",
        {
            "object_family": object_family,
            "organization_profile_id": requesting_org,
            "session_status": status,
        },
    )
    return _json_safe(
        {
            "allowed": True,
            "reason": "same_org_session_ok",
            "object_family": object_family,
            "live_access_claimed": False,
            "external_users_can_access_claimed": False,
            "production_multi_tenant_claimed": False,
            "note": "dry_run_or_fixture_only"
            if status in {"dry_run", "fixture_internal"}
            else "ok",
        }
    )


def resolve_controlled_pilot_access(*, login_live: bool = False) -> dict[str, Any]:
    return _json_safe(
        {
            "controlled_pilot_access_allowed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "login_live_claimed": False,
            "production_multi_tenant_claimed": False,
            "external_users_can_access_claimed": False,
            "reason": "auth_gates_incomplete"
            if not login_live
            else "still_blocked_pending_storage_policy",
        }
    )


def run_session_tenant_enforcement_suite() -> dict[str, Any]:
    dry = build_session_context(status="dry_run", organization_profile_id="org_a")
    expired = build_session_context(status="expired", organization_profile_id="org_a")
    invalid = build_session_context(status="invalid", organization_profile_id="org_a")
    customer = build_session_context(
        status="dry_run",
        organization_profile_id="org_a",
        role="customer_user",
        context_kind="customer",
    )

    cases = []
    fails: list[str] = []

    e = enforce_session_object_access(
        session=expired,
        object_family="evidence_intake_lifecycle",
        resource_org_id="org_a",
    )
    if e["allowed"]:
        fails.append("expired_allowed")
    cases.append(e)

    i = enforce_session_object_access(
        session=invalid, object_family="package_workspace", resource_org_id="org_a"
    )
    if i["allowed"]:
        fails.append("invalid_allowed")
    cases.append(i)

    if dry.get("live_access_claimed"):
        fails.append("dry_run_live_claim")

    op = enforce_session_object_access(
        session=customer,
        object_family="operator_readiness",
        resource_org_id="org_a",
    )
    if op["allowed"]:
        fails.append("customer_accessed_operator")
    cases.append(op)

    cross_families = (
        "evidence_intake_lifecycle",
        "customer_data_policy",
        "applicant_authority",
        "package_export_preview",
    )
    for fam in cross_families:
        cross = enforce_session_object_access(
            session=customer, object_family=fam, resource_org_id="org_b", action="view"
        )
        if cross["allowed"]:
            fails.append(f"cross_org_allowed:{fam}")
        cases.append(cross)

    collab = enforce_session_object_access(
        session=customer,
        object_family="collaboration_settings",
        resource_org_id="org_a",
        action="manage_collaboration",
    )
    if collab["allowed"]:
        fails.append("collaboration_allowed_while_off")
    cases.append(collab)

    pilot = resolve_controlled_pilot_access(login_live=False)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "suite_status": "PASS" if not fails else "FAIL",
            "fails": fails,
            "protected_object_families": list(PROTECTED_OBJECT_FAMILIES),
            "session_statuses": list(SESSION_STATUSES),
            "cases_run": len(cases),
            "denial_audit_events_present": any(
                e.get("event") in {"session_deny", "cross_org_deny"} for e in _AUDIT
            ),
            "controlled_pilot_access": pilot,
            "production_multi_tenant_claimed": False,
            "external_users_can_access_claimed": False,
            "login_live_claimed": False,
            "controlled_customer_pilot_status": "NO_GO",
        }
    )


def session_tenant_enforcement_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_multi_tenant_claimed",
        "external_users_can_access_claimed",
        "login_live_claimed",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    if result.get("suite_status") == "FAIL":
        fails.extend(result.get("fails") or ["suite_fail"])
    return fails


def get_session_tenant_audit_events() -> list[dict[str, Any]]:
    return list(_AUDIT)


def clear_session_tenant_audit_for_tests() -> None:
    _AUDIT.clear()

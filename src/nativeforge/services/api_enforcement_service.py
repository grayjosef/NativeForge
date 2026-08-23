"""API-layer enforcement seam (Gate 58).

Gate 51-57 produced tenant, authority, RBAC and discovery contracts. Those
contracts protect nothing unless the request path calls them. This module is the
single seam a handler (or a handler adapter) calls, so enforcement is one
function rather than a convention repeated per route.

Framework-agnostic on purpose: every function returns a **decision**, never
raises an HTTP error. The FastAPI adapter in ``nativeforge.api.tenant_guard``
translates a denial into the status code each existing call site already
returns, so wiring the seam in changes no API behaviour.

Deny by default. Missing tenant, missing role, missing membership, missing or
unknown authority all deny.

Audit events are **modeled, not stored** — every event carries
``persisted: false``. Customer persistence is not live and this must not be
mistaken for an audit log.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.authority_proof_workflow_service import (
    AUTHORITY_SENSITIVE_ACTIONS,
    evaluate_authority_sensitive_action,
)
from nativeforge.services.continuous_source_discovery_service import (
    evaluate_source_promotion,
)
from nativeforge.services.org_tenant_seat_model_service import (
    ALL_ROLES,
    INTERNAL_ROLES,
    MEMBERSHIP_STATES,
    evaluate_seat_invite,
    evaluate_tenant_scoped_access,
    make_audit_event,
)
from nativeforge.services.rbac_privilege_matrix_service import (
    PERMANENTLY_BLOCKED_CAPABILITIES,
    evaluate_capability,
)

SCHEMA_VERSION = "nf_api_enforcement_v1"

# Membership states that may act at all.
ACTIVE_MEMBERSHIP_STATES = frozenset({"active"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_request_enforcement_context(
    *,
    requesting_org_id: str | None,
    actor_id: str | None,
    actor_role: str | None = None,
    membership_state: str | None = None,
    plane: str = "unknown",
    authority_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize a request into an enforcement context.

    Anything absent or unrecognized is normalized to a denying value rather
    than to a permissive default.
    """
    role = actor_role if actor_role in ALL_ROLES else "unknown"
    mem = membership_state if membership_state in MEMBERSHIP_STATES else "unknown"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "requesting_org_id": (requesting_org_id or "").strip(),
            "actor_id": (actor_id or "").strip(),
            "actor_role": role,
            "membership_state": mem,
            "plane": plane,
            "has_tenant": bool((requesting_org_id or "").strip()),
            "has_actor": bool((actor_id or "").strip()),
            "role_known": role != "unknown",
            "membership_active": mem in ACTIVE_MEMBERSHIP_STATES,
            "is_internal_role": role in INTERNAL_ROLES,
            "authority_proof": authority_proof,
            # Honest boundaries.
            "login_live_claimed": False,
            "production_storage_claimed": False,
            "customer_persistence_claimed": False,
        }
    )


def _base_denials(context: dict[str, Any], *, require_role: bool) -> list[str]:
    reasons: list[str] = []
    if not context.get("has_tenant"):
        reasons.append("missing_tenant")
    if not context.get("has_actor"):
        reasons.append("missing_actor")
    if require_role:
        if not context.get("role_known"):
            reasons.append("missing_or_unknown_role")
        if not context.get("membership_active"):
            reasons.append("membership_not_active")
    return reasons


def enforce_tenant_access(
    *,
    context: dict[str, Any],
    resource_org_id: str | None,
    object_type: str,
    action: str,
) -> dict[str, Any]:
    """Enforce org-scoped access before a tenant-scoped read or write."""
    reasons = _base_denials(context, require_role=False)
    audit: list[dict[str, Any]] = []

    res = (resource_org_id or "").strip()
    if not res:
        reasons.append("missing_resource_org")

    inner: dict[str, Any] | None = None
    if not reasons:
        inner = evaluate_tenant_scoped_access(
            requesting_org_id=str(context.get("requesting_org_id")),
            resource_org_id=res,
            object_type=object_type,
            action=action,
            actor_id=str(context.get("actor_id")),
            actor_role=str(context.get("actor_role")),
        )
        if not inner.get("allowed"):
            reasons.append("cross_org_denied")
        audit.extend(inner.get("audit_events") or [])
    else:
        audit.append(
            make_audit_event(
                event_type="tenant_access_denied",
                organization_profile_id=str(context.get("requesting_org_id") or ""),
                actor_id=str(context.get("actor_id") or ""),
                detail={
                    "object_type": object_type,
                    "action": action,
                    "reasons": reasons,
                },
            )
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "enforcement": "tenant_access",
            "allowed": not reasons,
            "blocked_reasons": reasons,
            "object_type": object_type,
            "action": action,
            "inner_decision": inner,
            "audit_events": audit,
        }
    )


def enforce_capability(
    *,
    context: dict[str, Any],
    capability: str,
    missing_evidence: list[str] | None = None,
) -> dict[str, Any]:
    """Enforce a role capability, including the authority gate where it applies."""
    reasons = _base_denials(context, require_role=True)
    audit: list[dict[str, Any]] = []

    # Production gates are unreachable regardless of context.
    if capability in PERMANENTLY_BLOCKED_CAPABILITIES:
        reasons.append("capability_permanently_blocked_at_this_stage")
        detail = None
    else:
        detail = evaluate_capability(
            role=str(context.get("actor_role")),
            capability=capability,
            authority_proof=context.get("authority_proof"),
            missing_evidence=missing_evidence,
        )
        if not detail.get("allowed"):
            reasons.extend(detail.get("blocked_reasons") or [])

    if reasons:
        audit.append(
            make_audit_event(
                event_type="authority_sensitive_action_blocked",
                organization_profile_id=str(context.get("requesting_org_id") or ""),
                actor_id=str(context.get("actor_id") or ""),
                detail={"capability": capability, "reasons": reasons},
            )
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "enforcement": "capability",
            "allowed": not reasons,
            "blocked_reasons": reasons,
            "capability": capability,
            "capability_detail": detail,
            "carries_customer_authority": bool(
                not reasons and not context.get("is_internal_role")
            ),
            "audit_events": audit,
        }
    )


def enforce_authority_sensitive_action(
    *,
    context: dict[str, Any],
    action: str,
    missing_evidence: list[str] | None = None,
) -> dict[str, Any]:
    """Enforce a verified-authority requirement before an authority action."""
    reasons = _base_denials(context, require_role=True)
    audit: list[dict[str, Any]] = []

    if action not in AUTHORITY_SENSITIVE_ACTIONS:
        reasons.append("action_not_recognized_as_authority_sensitive")

    proof = context.get("authority_proof")
    detail: dict[str, Any] | None = None
    if proof is None:
        reasons.append("authority_proof_absent")
    else:
        detail = evaluate_authority_sensitive_action(
            action=action, proof=proof, missing_evidence=missing_evidence
        )
        if not detail.get("allowed"):
            reasons.extend(detail.get("blocked_reasons") or [])

    # Internal support never carries customer authority, whatever it can read.
    if context.get("is_internal_role"):
        reasons.append("internal_role_cannot_hold_customer_authority")

    if reasons:
        audit.append(
            make_audit_event(
                event_type="authority_sensitive_action_blocked",
                organization_profile_id=str(context.get("requesting_org_id") or ""),
                actor_id=str(context.get("actor_id") or ""),
                detail={"action": action, "reasons": reasons},
            )
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "enforcement": "authority_sensitive_action",
            "allowed": not reasons,
            "blocked_reasons": reasons,
            "action": action,
            "authority_detail": detail,
            "final_eligibility_claimed": False,
            "submission_ready_claimed": False,
            "audit_events": audit,
        }
    )


def enforce_seat_invite(
    *,
    context: dict[str, Any],
    tenant: dict[str, Any],
    invitee_id: str,
    invitee_role: str,
    override_approved_by: str | None = None,
) -> dict[str, Any]:
    """Enforce seat-cap and role rules before an invite is created."""
    reasons = _base_denials(context, require_role=True)
    audit: list[dict[str, Any]] = []

    cap_check = enforce_capability(context=context, capability="manage_seats")
    if not cap_check.get("allowed"):
        reasons.append("actor_cannot_manage_seats")
        audit.extend(cap_check.get("audit_events") or [])

    detail: dict[str, Any] | None = None
    if not reasons:
        detail = evaluate_seat_invite(
            tenant=tenant,
            invitee_id=invitee_id,
            role=invitee_role,
            actor_id=str(context.get("actor_id")),
            override_approved_by=override_approved_by,
        )
        audit.extend(detail.get("audit_events") or [])
        if not detail.get("allowed"):
            reasons.append(str(detail.get("reason") or "seat_invite_denied"))

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "enforcement": "seat_invite",
            "allowed": not reasons,
            "blocked_reasons": reasons,
            "invite_detail": detail,
            "audit_events": audit,
        }
    )


def enforce_source_promotion(
    *,
    context: dict[str, Any],
    candidate: dict[str, Any],
    approver_id: str | None = None,
) -> dict[str, Any]:
    """Enforce review before a source candidate reaches monitoring."""
    reasons = _base_denials(context, require_role=True)
    audit: list[dict[str, Any]] = []

    detail = evaluate_source_promotion(candidate=candidate, approver_id=approver_id)
    if not detail.get("allowed"):
        reasons.extend(detail.get("blocked_reasons") or [])
    if detail.get("audit_event"):
        audit.append(detail["audit_event"])

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "enforcement": "source_promotion",
            "allowed": not reasons,
            "blocked_reasons": reasons,
            "promotion_detail": detail,
            "live_ingest_claimed": False,
            "audit_events": audit,
        }
    )


def enforcement_decision_invariant_failures(decision: dict[str, Any]) -> list[str]:
    """A decision must never be allowed while carrying blocked reasons."""
    fails: list[str] = []
    if decision.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if decision.get("allowed") and decision.get("blocked_reasons"):
        fails.append("allowed_with_blocked_reasons")
    if not decision.get("allowed") and not decision.get("blocked_reasons"):
        fails.append("denied_without_reason")
    # A denial must always be auditable.
    if not decision.get("allowed") and not decision.get("audit_events"):
        fails.append("denial_without_audit_event")
    for ev in decision.get("audit_events") or []:
        if ev.get("persisted") is not False:
            fails.append("audit_event_claims_persistence")
    return fails

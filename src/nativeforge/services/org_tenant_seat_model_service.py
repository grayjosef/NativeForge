"""Organization tenant + seat model (Gate 51).

One organization = one tenant. Deny by default, org-scoped by default.

This composes with, and does not replace, the existing
``tenant_boundary_enforcement_service`` (Block 31) and
``rbac_policy_contract_service`` (Block 35). Those remain the enforcement
primitives; this module adds the organization seat/membership/invite model that
Gate 51 requires.

Nothing here implies production storage, live customer login, or customer
persistence. These are in-memory contracts evaluated from caller-supplied state.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.tenant_boundary_enforcement_service import (
    assert_tenant_access,
)

SCHEMA_VERSION = "nf_org_tenant_seat_model_v1"

DEFAULT_SEAT_CAP = 5

# Gate 51 customer-facing roles plus the internal support role.
ORG_ROLES = frozenset(
    {
        "org_owner",
        "org_admin",
        "authorized_representative",
        "grant_lead",
        "reviewer",
        "viewer",
    }
)

INTERNAL_ROLES = frozenset({"operator_internal"})

ALL_ROLES = ORG_ROLES | INTERNAL_ROLES | {"unknown"}

# Roles that occupy a customer seat. operator_internal is support access and is
# deliberately excluded: internal staff must never consume a customer seat, and
# must never be implied to carry customer authority.
SEAT_CONSUMING_ROLES = ORG_ROLES

INVITE_STATES = frozenset(
    {
        "draft",
        "blocked_seat_limit",
        "pending_override_approval",
        "sent",
        "accepted",
        "revoked",
        "expired",
        "unknown",
    }
)

MEMBERSHIP_STATES = frozenset(
    {"invited", "active", "suspended", "removed", "unknown"}
)

# Object families that are strictly org-scoped. Superset of the Block 31 list,
# extended with the Gate 54/55 discovery objects.
TENANT_SCOPED_OBJECTS = frozenset(
    {
        "org_profile",
        "workspace",
        "opportunity_shortlist",
        "evidence_intake",
        "evidence_lifecycle",
        "package_workspace",
        "checklist",
        "binder",
        "draft_workspace",
        "feedback_report",
        "package_export_preview",
        "applicant_authority",
        "authority_proof",
        "audit_event",
        "source_candidate_note",
        "discovery_shortlist",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_tenant_id(organization_profile_id: str) -> str:
    raw = f"tenant::{organization_profile_id}".encode()
    return f"tn_{hashlib.sha256(raw).hexdigest()[:16]}"


def make_audit_event(
    *,
    event_type: str,
    organization_profile_id: str,
    actor_id: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Modeled audit event. Not persisted — customer persistence is NOT live."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "event_type": event_type,
            "organization_profile_id": organization_profile_id,
            "tenant_id": make_tenant_id(organization_profile_id),
            "actor_id": actor_id,
            "detail": dict(detail or {}),
            "persisted": False,
            "persistence_claimed": False,
        }
    )


def build_org_tenant(
    *,
    organization_profile_id: str,
    display_name: str,
    seat_cap: int = DEFAULT_SEAT_CAP,
    memberships: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build an organization tenant record with its seat ledger."""
    mem = [dict(m) for m in (memberships or [])]
    for m in mem:
        if m.get("role") not in ALL_ROLES:
            m["role"] = "unknown"
        if m.get("state") not in MEMBERSHIP_STATES:
            m["state"] = "unknown"

    occupying = [
        m
        for m in mem
        if m.get("state") in {"invited", "active"}
        and m.get("role") in SEAT_CONSUMING_ROLES
    ]
    cap = seat_cap if isinstance(seat_cap, int) and seat_cap > 0 else DEFAULT_SEAT_CAP

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_profile_id": organization_profile_id,
            "tenant_id": make_tenant_id(organization_profile_id),
            "display_name": display_name,
            "seat_cap": cap,
            "seat_cap_is_default": cap == DEFAULT_SEAT_CAP,
            "seats_used": len(occupying),
            "seats_available": max(0, cap - len(occupying)),
            "memberships": mem,
            "internal_support_members": [
                m for m in mem if m.get("role") in INTERNAL_ROLES
            ],
            # Honest boundaries.
            "production_storage_claimed": False,
            "customer_persistence_claimed": False,
            "login_live_claimed": False,
        }
    )


def evaluate_seat_invite(
    *,
    tenant: dict[str, Any],
    invitee_id: str,
    role: str,
    actor_id: str,
    override_approved_by: str | None = None,
) -> dict[str, Any]:
    """Decide whether a seat invite is allowed.

    The sixth seat is blocked by default. An override must be explicitly
    approved and is always audited.
    """
    audit: list[dict[str, Any]] = []
    org = str(tenant.get("organization_profile_id") or "")
    normalized_role = role if role in ALL_ROLES else "unknown"

    # Internal support never consumes a seat and never implies customer authority.
    if normalized_role in INTERNAL_ROLES:
        audit.append(
            make_audit_event(
                event_type="seat_invite_created",
                organization_profile_id=org,
                actor_id=actor_id,
                detail={
                    "invitee_id": invitee_id,
                    "role": normalized_role,
                    "consumes_seat": False,
                    "customer_authority_implied": False,
                },
            )
        )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "allowed": True,
                "invite_state": "sent",
                "consumes_seat": False,
                "role": normalized_role,
                "carries_customer_authority": False,
                "reason": "internal_support_role_does_not_consume_seat",
                "audit_events": audit,
            }
        )

    if normalized_role == "unknown":
        audit.append(
            make_audit_event(
                event_type="seat_invite_blocked_limit",
                organization_profile_id=org,
                actor_id=actor_id,
                detail={"invitee_id": invitee_id, "reason": "unknown_role"},
            )
        )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "invite_state": "blocked_seat_limit",
                "consumes_seat": False,
                "role": normalized_role,
                "carries_customer_authority": False,
                "reason": "unknown_role_denied",
                "audit_events": audit,
            }
        )

    used = int(tenant.get("seats_used") or 0)
    cap = int(tenant.get("seat_cap") or DEFAULT_SEAT_CAP)

    if used < cap:
        audit.append(
            make_audit_event(
                event_type="seat_invite_created",
                organization_profile_id=org,
                actor_id=actor_id,
                detail={
                    "invitee_id": invitee_id,
                    "role": normalized_role,
                    "seats_used_before": used,
                    "seat_cap": cap,
                },
            )
        )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "allowed": True,
                "invite_state": "sent",
                "consumes_seat": True,
                "role": normalized_role,
                "carries_customer_authority": False,
                "reason": "within_seat_cap",
                "audit_events": audit,
            }
        )

    # At or over cap.
    if not override_approved_by:
        audit.append(
            make_audit_event(
                event_type="seat_invite_blocked_limit",
                organization_profile_id=org,
                actor_id=actor_id,
                detail={
                    "invitee_id": invitee_id,
                    "role": normalized_role,
                    "seats_used": used,
                    "seat_cap": cap,
                },
            )
        )
        audit.append(
            make_audit_event(
                event_type="seat_limit_override_requested",
                organization_profile_id=org,
                actor_id=actor_id,
                detail={"invitee_id": invitee_id, "seat_cap": cap},
            )
        )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "invite_state": "blocked_seat_limit",
                "consumes_seat": False,
                "role": normalized_role,
                "carries_customer_authority": False,
                "reason": "seat_cap_reached_override_required",
                "audit_events": audit,
            }
        )

    audit.append(
        make_audit_event(
            event_type="seat_limit_override_approved",
            organization_profile_id=org,
            actor_id=actor_id,
            detail={
                "invitee_id": invitee_id,
                "approved_by": override_approved_by,
                "seat_cap": cap,
                "seats_used": used,
            },
        )
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "allowed": True,
            "invite_state": "pending_override_approval",
            "consumes_seat": True,
            "role": normalized_role,
            "carries_customer_authority": False,
            "reason": "seat_cap_override_approved",
            "override_approved_by": override_approved_by,
            "audit_events": audit,
        }
    )


def evaluate_tenant_scoped_access(
    *,
    requesting_org_id: str,
    resource_org_id: str,
    object_type: str,
    action: str,
    actor_id: str,
    actor_role: str = "unknown",
) -> dict[str, Any]:
    """Deny-by-default org-scoped access, with a cross-org audit event.

    Delegates the core same-org decision to the Block 31 primitive so there is
    one enforcement rule, not two that can drift apart.
    """
    inner = assert_tenant_access(
        requesting_org_id=requesting_org_id,
        resource_org_id=resource_org_id,
        object_type=object_type,
        action=action,
    )
    allowed = bool(inner.get("allowed"))
    scoped = object_type in TENANT_SCOPED_OBJECTS

    audit: list[dict[str, Any]] = []
    if not allowed:
        audit.append(
            make_audit_event(
                event_type="cross_org_access_attempt",
                organization_profile_id=requesting_org_id,
                actor_id=actor_id,
                detail={
                    "resource_org_id": resource_org_id,
                    "object_type": object_type,
                    "action": action,
                    "actor_role": actor_role,
                },
            )
        )
        audit.append(
            make_audit_event(
                event_type="tenant_access_denied",
                organization_profile_id=requesting_org_id,
                actor_id=actor_id,
                detail={"object_type": object_type, "action": action},
            )
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "allowed": allowed,
            "object_type": object_type,
            "object_is_tenant_scoped": scoped,
            "action": action,
            "requesting_org_id": requesting_org_id,
            "resource_org_id": resource_org_id,
            "inner_decision": inner,
            "audit_events": audit,
        }
    )


def org_tenant_invariant_failures(tenant: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if tenant.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    cap = tenant.get("seat_cap")
    if not isinstance(cap, int) or cap < 1:
        fails.append("seat_cap_invalid")
    used = tenant.get("seats_used")
    if not isinstance(used, int) or used < 0:
        fails.append("seats_used_invalid")
    for m in tenant.get("memberships") or []:
        if m.get("role") not in ALL_ROLES:
            fails.append("membership_role_unknown")
        if m.get("state") not in MEMBERSHIP_STATES:
            fails.append("membership_state_unknown")
    # An internal support member must never be counted as a customer seat.
    for m in tenant.get("internal_support_members") or []:
        if m.get("role") not in INTERNAL_ROLES:
            fails.append("internal_support_member_role_invalid")
    if tenant.get("production_storage_claimed") is not False:
        fails.append("production_storage_claimed")
    if tenant.get("customer_persistence_claimed") is not False:
        fails.append("customer_persistence_claimed")
    if tenant.get("login_live_claimed") is not False:
        fails.append("login_live_claimed")
    return fails

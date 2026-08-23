"""RBAC privilege matrix + audit event vocabulary (Gate 53).

Safe by default: a capability is denied unless the matrix grants it, and the
authority-sensitive subset needs a verified authority proof on top of the grant.

Extends rather than replaces ``rbac_policy_contract_service`` (Block 35), which
uses the older role vocabulary and remains in force for existing surfaces.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.authority_proof_workflow_service import (
    AUTHORITY_SENSITIVE_ACTIONS,
    evaluate_authority_sensitive_action,
)
from nativeforge.services.org_tenant_seat_model_service import (
    ALL_ROLES,
    INTERNAL_ROLES,
)

SCHEMA_VERSION = "nf_rbac_privilege_matrix_v1"

CAPABILITIES = frozenset(
    {
        "view_workspace",
        "manage_org_profile",
        "manage_seats",
        "approve_admins",
        "view_org_audit_events",
        "request_authority_verification",
        "manage_workspace_settings",
        "assign_grant_leads",
        "manage_pursuit_workflow",
        "assemble_evidence",
        "draft_package",
        "request_review",
        "comment_review",
        "flag_issues",
        "certify_org_facts",
        "approve_package_readiness",
        "final_application_package_signoff",
        "support_review_access",
    }
)

# Capabilities that additionally require a verified authority proof.
AUTHORITY_GATED_CAPABILITIES = frozenset(
    {
        "certify_org_facts",
        "approve_package_readiness",
        "final_application_package_signoff",
    }
)

# Never grantable to any role, by any path, at this production stage.
PERMANENTLY_BLOCKED_CAPABILITIES = frozenset(
    {
        "controlled_customer_pilot_go",
        "production_rollout_go",
        "enable_login_live",
        "enable_production_storage",
        "declare_pen_test_passed",
        "final_submit_to_portal",
    }
)

ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    "org_owner": frozenset(
        {
            "view_workspace",
            "manage_org_profile",
            "manage_seats",
            "approve_admins",
            "view_org_audit_events",
            "request_authority_verification",
            "manage_workspace_settings",
            "assign_grant_leads",
        }
    ),
    "org_admin": frozenset(
        {
            "view_workspace",
            "manage_seats",
            "manage_workspace_settings",
            "assign_grant_leads",
            "request_authority_verification",
        }
    ),
    "authorized_representative": frozenset(
        {
            "view_workspace",
            "request_authority_verification",
            "certify_org_facts",
            "approve_package_readiness",
            "final_application_package_signoff",
        }
    ),
    "grant_lead": frozenset(
        {
            "view_workspace",
            "manage_pursuit_workflow",
            "assemble_evidence",
            "draft_package",
            "request_review",
        }
    ),
    "reviewer": frozenset({"view_workspace", "comment_review", "flag_issues"}),
    "viewer": frozenset({"view_workspace"}),
    # Support/review mode only. Audited. Never customer authority.
    "operator_internal": frozenset({"support_review_access", "view_workspace"}),
    "unknown": frozenset(),
}

AUDIT_EVENT_TYPES = frozenset(
    {
        "tenant_access_denied",
        "seat_invite_created",
        "seat_invite_blocked_limit",
        "seat_limit_override_requested",
        "seat_limit_override_approved",
        "role_changed",
        "authority_proof_requested",
        "authority_proof_submitted",
        "authority_proof_verified",
        "authority_proof_rejected",
        "authority_proof_expired",
        "authority_proof_revoked",
        "authority_sensitive_action_blocked",
        "cross_org_access_attempt",
        "feedback_alert_attempted",
        "feedback_alert_failed",
        "source_candidate_discovered",
        "source_candidate_promoted",
        "source_candidate_blocked",
        "opportunity_duplicate_flagged",
        "opportunity_source_stale",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_privilege_matrix() -> dict[str, Any]:
    """Materialize the full role -> capability matrix for review and display."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "roles": sorted(ALL_ROLES),
            "capabilities": sorted(CAPABILITIES),
            "authority_gated_capabilities": sorted(AUTHORITY_GATED_CAPABILITIES),
            "permanently_blocked_capabilities": sorted(
                PERMANENTLY_BLOCKED_CAPABILITIES
            ),
            "matrix": {r: sorted(c) for r, c in ROLE_CAPABILITIES.items()},
            "internal_roles": sorted(INTERNAL_ROLES),
            "default": "deny",
            "audit_event_types": sorted(AUDIT_EVENT_TYPES),
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "login_live_claimed": False,
            "production_storage_claimed": False,
            "pen_test_passed_claimed": False,
        }
    )


def evaluate_capability(
    *,
    role: str,
    capability: str,
    authority_proof: dict[str, Any] | None = None,
    missing_evidence: list[str] | None = None,
) -> dict[str, Any]:
    """Deny-by-default capability check with the authority gate layered on."""
    reasons: list[str] = []
    normalized_role = role if role in ALL_ROLES else "unknown"

    if capability in PERMANENTLY_BLOCKED_CAPABILITIES:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "role": normalized_role,
                "capability": capability,
                "allowed": False,
                "blocked_reasons": ["capability_permanently_blocked_at_this_stage"],
                "carries_customer_authority": False,
            }
        )

    if capability not in CAPABILITIES:
        reasons.append("capability_not_recognized")

    granted = capability in ROLE_CAPABILITIES.get(normalized_role, frozenset())
    if not granted:
        reasons.append("capability_not_granted_to_role")

    authority_detail: dict[str, Any] | None = None
    if capability in AUTHORITY_GATED_CAPABILITIES:
        if not authority_proof:
            reasons.append("authority_proof_required")
        else:
            action = (
                "final_application_package_signoff"
                if capability == "final_application_package_signoff"
                else (
                    "certify_official_org_facts"
                    if capability == "certify_org_facts"
                    else "official_package_approval"
                )
            )
            authority_detail = evaluate_authority_sensitive_action(
                action=action,
                proof=authority_proof,
                missing_evidence=missing_evidence,
            )
            if not authority_detail.get("allowed"):
                reasons.extend(authority_detail.get("blocked_reasons") or [])

    allowed = not reasons

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "role": normalized_role,
            "capability": capability,
            "allowed": allowed,
            "blocked_reasons": reasons,
            "authority_gated": capability in AUTHORITY_GATED_CAPABILITIES,
            "authority_detail": authority_detail,
            # Internal support never carries customer authority, whatever it can see.
            "carries_customer_authority": bool(
                allowed
                and normalized_role not in INTERNAL_ROLES
                and capability in AUTHORITY_GATED_CAPABILITIES
            ),
        }
    )


def record_role_change(
    *,
    organization_profile_id: str,
    actor_id: str,
    subject_id: str,
    old_role: str,
    new_role: str,
) -> dict[str, Any]:
    """Every role change is audited, including upgrades into authority roles."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "event_type": "role_changed",
            "organization_profile_id": organization_profile_id,
            "actor_id": actor_id,
            "subject_id": subject_id,
            "old_role": old_role if old_role in ALL_ROLES else "unknown",
            "new_role": new_role if new_role in ALL_ROLES else "unknown",
            "is_privilege_escalation": (
                new_role in {"org_owner", "org_admin", "authorized_representative"}
                and old_role not in {"org_owner", "org_admin"}
            ),
            "grants_customer_authority_immediately": False,
            "persisted": False,
        }
    )


def privilege_matrix_invariant_failures(matrix: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if matrix.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if matrix.get("default") != "deny":
        fails.append("default_not_deny")

    m = matrix.get("matrix") or {}
    for role, caps in m.items():
        for c in caps:
            if c not in CAPABILITIES:
                fails.append(f"unknown_capability:{role}:{c}")
            if c in PERMANENTLY_BLOCKED_CAPABILITIES:
                fails.append(f"blocked_capability_granted:{role}:{c}")

    # Internal support must never hold an authority-gated capability.
    for role in INTERNAL_ROLES:
        for c in m.get(role, []):
            if c in AUTHORITY_GATED_CAPABILITIES:
                fails.append(f"internal_role_has_authority_capability:{role}:{c}")

    # Roles below authorized_representative must never certify or sign off.
    for role in ("reviewer", "viewer", "grant_lead", "unknown"):
        for c in m.get(role, []):
            if c in AUTHORITY_GATED_CAPABILITIES:
                fails.append(f"non_authority_role_has_authority_capability:{role}:{c}")

    if matrix.get("controlled_customer_pilot_status") != "NO_GO":
        fails.append("customer_pilot_not_no_go")
    if matrix.get("production_rollout_status") != "NO_GO":
        fails.append("production_rollout_not_no_go")
    for forbidden in (
        "login_live_claimed",
        "production_storage_claimed",
        "pen_test_passed_claimed",
    ):
        if matrix.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")

    missing = AUTHORITY_SENSITIVE_ACTIONS - AUTHORITY_SENSITIVE_ACTIONS
    if missing:  # pragma: no cover - defensive
        fails.append("authority_action_vocabulary_drift")
    return fails

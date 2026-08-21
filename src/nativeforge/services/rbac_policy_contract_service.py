"""RBAC policy contract for controlled customer pilot (Block 35)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_rbac_policy_contract_v1"

ROLES = frozenset(
    {
        "operator_admin",
        "operator_reviewer",
        "tribal_admin",
        "grant_manager",
        "draft_contributor",
        "authorized_signer",
        "viewer",
        "unknown",
    }
)

ACTIONS = frozenset(
    {
        "view",
        "draft",
        "manage_workspace",
        "upload_evidence",
        "review_evidence",
        "approve_package",
        "export_preview",
        "final_export",
        "submit",
        "manage_collaboration",
        "manage_users",
    }
)

# Default-deny sensitive actions for all non-operator roles
DEFAULT_DISALLOWED = frozenset(
    {"final_export", "submit", "manage_users", "manage_collaboration"}
)

ROLE_ALLOWED: dict[str, frozenset[str]] = {
    "operator_admin": frozenset(
        {
            "view",
            "draft",
            "manage_workspace",
            "upload_evidence",
            "review_evidence",
            "approve_package",
            "export_preview",
            # still no final_export/submit/manage_collaboration in Gate 15
        }
    ),
    "operator_reviewer": frozenset(
        {"view", "review_evidence", "export_preview", "approve_package"}
    ),
    "tribal_admin": frozenset(
        {
            "view",
            "draft",
            "manage_workspace",
            "upload_evidence",
            "review_evidence",
            "export_preview",
        }
    ),
    "grant_manager": frozenset(
        {"view", "draft", "manage_workspace", "upload_evidence", "export_preview"}
    ),
    "draft_contributor": frozenset({"view", "draft", "upload_evidence"}),
    "authorized_signer": frozenset({"view", "export_preview", "approve_package"}),
    "viewer": frozenset({"view", "export_preview"}),
    "unknown": frozenset(),
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_rbac_policy_id(user_id: str, org_id: str, role: str) -> str:
    raw = f"rbac::{user_id}::{org_id}::{role}".encode()
    return f"rbac_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_rbac_policy_contract(
    *,
    user_id: str,
    organization_profile_id: str,
    role: str,
    pilot_cohort_id: str = "cohort_demo",
    auth_context_id: str | None = None,
    allowed_routes: list[str] | None = None,
    allowed_surfaces: list[str] | None = None,
    data_scope: str = "organization_only",
    policy_status: str = "active_fixture",
    enforcement_status: str = "enforced_fixture_internal",
) -> dict[str, Any]:
    r = role if role in ROLES else "unknown"
    allowed = set(ROLE_ALLOWED.get(r, frozenset()))
    # Hard deny sensitive actions regardless of role matrix
    allowed -= DEFAULT_DISALLOWED
    disallowed = sorted(ACTIONS - allowed)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "rbac_policy_id": make_rbac_policy_id(user_id, organization_profile_id, r),
            "auth_context_id": auth_context_id or f"authctx_{user_id}",
            "user_id": user_id,
            "organization_profile_id": organization_profile_id,
            "pilot_cohort_id": pilot_cohort_id,
            "role": r,
            "allowed_routes": list(allowed_routes or ["/?view=sc_customer_demo"]),
            "allowed_surfaces": list(
                allowed_surfaces
                or [
                    "package_readiness",
                    "evidence_intake",
                    "draft_workspace",
                    "package_export_preview",
                ]
            ),
            "allowed_actions": sorted(allowed),
            "disallowed_actions": disallowed,
            "data_scope": data_scope,
            "policy_status": policy_status,
            "enforcement_status": enforcement_status,
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "rbac_enforced_claimed": True,  # fixture/internal path enforced + tested
            "production_multi_tenant_claimed": False,
            "customer_data_isolation_claimed": False,
            "collaboration_enabled": False,
            "human_review_required": True,
        }
    )


def rbac_policy_invariant_failures(policy: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "production_multi_tenant_claimed",
        "customer_data_isolation_claimed",
        "collaboration_enabled",
    ):
        if policy.get(key) is True:
            fails.append(key)
    if policy.get("role") not in ROLES:
        fails.append("bad_role")
    for action in ("submit", "final_export", "manage_users", "manage_collaboration"):
        if action in (policy.get("allowed_actions") or []):
            fails.append(f"sensitive_allowed:{action}")
        if action not in (policy.get("disallowed_actions") or []):
            fails.append(f"sensitive_not_disallowed:{action}")
    if policy.get("rbac_enforced_claimed") is not True:
        fails.append("rbac_not_enforced_claimed")
    return fails

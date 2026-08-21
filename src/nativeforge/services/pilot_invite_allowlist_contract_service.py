"""Controlled pilot invite / allowlist contract (Block 37)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_pilot_invite_allowlist_contract_v1"

INVITE_STATUSES = frozenset(
    {
        "draft",
        "pending_owner_approval",
        "blocked_missing_auth",
        "blocked_missing_storage",
        "blocked_missing_pen_test",
        "ready_for_internal_review",
        "ready_for_external_send",
        "sent",
        "revoked",
        "not_supported",
    }
)

DEFAULT_BLOCKED_ACTIONS = [
    "submit",
    "final_export",
    "manage_users",
    "manage_collaboration",
]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_pilot_invite_id(org_id: str, email: str, cohort_id: str) -> str:
    raw = f"pi::{org_id}::{email}::{cohort_id}".encode()
    return f"pi_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_pilot_invite_contract(
    *,
    organization_profile_id: str,
    invitee_email: str,
    invitee_role: str = "viewer",
    pilot_cohort_id: str = "cohort_demo",
    invite_status: str = "draft",
    external_auth_configured: bool = False,
    storage_ready: bool = False,
    pen_test_passed: bool = False,
    operator_approval: bool = False,
) -> dict[str, Any]:
    status = invite_status if invite_status in INVITE_STATUSES else "draft"
    # Never default to sent; force blockers when deps missing
    if status == "sent" and not (
        external_auth_configured
        and storage_ready
        and pen_test_passed
        and operator_approval
    ):
        status = "blocked_missing_auth"
    if not external_auth_configured and status in {
        "ready_for_external_send",
        "sent",
    }:
        status = "blocked_missing_auth"
    if not storage_ready and status in {"ready_for_external_send", "sent"}:
        status = "blocked_missing_storage"
    if not pen_test_passed and status in {"ready_for_external_send", "sent"}:
        status = "blocked_missing_pen_test"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "pilot_invite_id": make_pilot_invite_id(
                organization_profile_id, invitee_email, pilot_cohort_id
            ),
            "organization_profile_id": organization_profile_id,
            "pilot_cohort_id": pilot_cohort_id,
            "invitee_email": invitee_email,
            "invitee_role": invitee_role,
            "allowed_routes": ["/?view=sc_customer_demo"],
            "allowed_surfaces": [
                "package_readiness",
                "evidence_intake",
                "package_export_preview",
            ],
            "allowed_actions": ["view", "export_preview"],
            "blocked_actions": list(DEFAULT_BLOCKED_ACTIONS),
            "invite_status": status,
            "auth_provider_required": "auth0_oidc",
            "external_auth_configured": bool(external_auth_configured),
            "login_live_claimed": False,
            "rbac_policy_reference": "nf_rbac_policy_contract_v1",
            "tenant_boundary_reference": "nf_tenant_boundary_enforcement_v1",
            "operator_approval_required": True,
            "pilot_go_claimed": False,
            "allowlist_required": True,
            "human_review_required": True,
        }
    )


def pilot_invite_contract_invariant_failures(invite: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if invite.get("invite_status") not in INVITE_STATUSES:
        fails.append("bad_status")
    if invite.get("invite_status") == "sent" and not invite.get(
        "external_auth_configured"
    ):
        fails.append("sent_without_auth")
    for key in ("login_live_claimed", "pilot_go_claimed"):
        if invite.get(key) is True:
            fails.append(key)
    if invite.get("operator_approval_required") is not True:
        fails.append("operator_approval_not_required")
    for action in ("submit", "final_export", "manage_users"):
        if action not in (invite.get("blocked_actions") or []):
            fails.append(f"missing_block:{action}")
    return fails

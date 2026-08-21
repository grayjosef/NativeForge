"""Controlled pilot invite design (Campaign Block 32)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_controlled_pilot_invite_design_v1"

PILOT_STATUSES = frozenset(
    {
        "not_ready",
        "blocked",
        "conditional_internal",
        "ready_for_invite_draft",
        "ready_for_controlled_customer",
        "not_supported",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_pilot_invite_design_id(label: str = "v1") -> str:
    raw = f"cpid::{label}".encode()
    return f"cpid_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_controlled_pilot_invite_design(
    *,
    storage_ready: bool = False,
    auth_ready: bool = False,
    rbac_ready: bool = False,
    tenant_isolation_ready: bool = False,
    pen_test_passed: bool = False,
    sca_passed: bool = False,
    customer_data_policy_ready: bool = False,
    support_feedback_ready: bool = True,
    operator_approval: bool = False,
) -> dict[str, Any]:
    preconditions = {
        "storage_readiness_dependency": storage_ready,
        "auth_dependency": auth_ready,
        "rbac_dependency": rbac_ready,
        "tenant_isolation_dependency": tenant_isolation_ready,
        "pen_test_sca_dependency": bool(pen_test_passed and sca_passed),
        "customer_data_policy_dependency": customer_data_policy_ready,
        "support_feedback_dependency": support_feedback_ready,
        "operator_approval_requirement": operator_approval,
    }
    all_ready = all(preconditions.values())
    if all_ready:
        status = "ready_for_controlled_customer"
    elif support_feedback_ready and not any(
        [
            storage_ready,
            auth_ready,
            rbac_ready,
            tenant_isolation_ready,
            pen_test_passed,
            sca_passed,
        ]
    ):
        status = "blocked"
    elif support_feedback_ready:
        status = "conditional_internal"
    else:
        status = "not_ready"

    # Gate 13 default: blocked / NO_GO for customer
    if status == "ready_for_controlled_customer" and not all_ready:
        status = "blocked"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "controlled_pilot_invite_design_id": make_pilot_invite_design_id(),
            "invite_status": "not_issued",
            "org_binding": "one_invite_to_one_organization_profile_id",
            "allowed_pilot_routes": ["/?view=sc_customer_demo"],
            "disallowed_surfaces": [
                "collaboration_matching",
                "production_admin",
                "cross_org_operator_override",
                "live_submit",
            ],
            "required_preconditions": preconditions,
            "pilot_status": status if status in PILOT_STATUSES else "blocked",
            "login_live_claimed": False,
            "controlled_customer_pilot_go": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "operator_approval_required": True,
            "buyer_summary": [
                "Controlled pilot invite design is complete; invites are not issued",
                "Customer pilot remains NO_GO until storage/auth/RBAC/tenant/pen-test/SCA pass",
                "External customer login is not live",
            ],
        }
    )


def controlled_pilot_invite_invariant_failures(design: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if design.get("pilot_status") not in PILOT_STATUSES:
        fails.append("bad_pilot_status")
    if design.get("login_live_claimed") is True:
        fails.append("login_live_claimed")
    if design.get("controlled_customer_pilot_go") is True:
        fails.append("controlled_customer_pilot_go")
    if design.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_status_go")
    if design.get("production_rollout_status") == "GO":
        fails.append("production_go")
    if design.get("invite_status") not in {"not_issued", "draft_only", "issued"}:
        fails.append("bad_invite_status")
    return fails

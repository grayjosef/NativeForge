"""Block 35 assembler: customer pilot auth/RBAC enforcement surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.auth_context_resolver_service import (
    auth_context_resolver_invariant_failures,
    resolve_auth_context,
)
from nativeforge.services.rbac_enforcement_service import (
    OBJECT_FAMILIES,
    run_rbac_enforcement_suite,
)
from nativeforge.services.rbac_policy_contract_service import (
    ACTIONS,
    ROLES,
    build_rbac_policy_contract,
    rbac_policy_invariant_failures,
)

SCHEMA_VERSION = "nf_rbac_enforcement_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_rbac_enforcement_demo_surface() -> dict[str, Any]:
    customer_ctx = resolve_auth_context(
        user_id="fixture_customer_demo",
        organization_profile_id="org_demo_sc",
        role="grant_manager",
        auth_mode="fixture_internal",
        context_kind="customer",
    )
    operator_ctx = resolve_auth_context(
        user_id="fixture_operator_demo",
        organization_profile_id="org_demo_sc",
        role="operator_reviewer",
        auth_mode="operator_demo",
        context_kind="operator",
    )
    policy = build_rbac_policy_contract(
        user_id="fixture_customer_demo",
        organization_profile_id="org_demo_sc",
        role="grant_manager",
    )
    suite = run_rbac_enforcement_suite()
    role_matrix = {
        role: build_rbac_policy_contract(
            user_id="matrix_user",
            organization_profile_id="org_demo_sc",
            role=role,
        )["allowed_actions"]
        for role in sorted(ROLES)
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 35,
            "title": "Customer pilot auth/RBAC enforcement path",
            "auth_mode": customer_ctx["auth_mode"],
            "login_live_claimed": False,
            "external_auth_configured": False,
            "production_auth_claimed": False,
            "rbac_enforced_claimed": True,
            "production_multi_tenant_claimed": False,
            "customer_data_isolation_claimed": False,
            "rbac_policy_status": policy["policy_status"],
            "enforcement_status": policy["enforcement_status"],
            "roles": sorted(ROLES),
            "actions": sorted(ACTIONS),
            "role_matrix": role_matrix,
            "denied_actions_default": sorted(
                {"submit", "final_export", "manage_users", "manage_collaboration"}
            ),
            "object_families_enforced": sorted(OBJECT_FAMILIES),
            "customer_auth_context": customer_ctx,
            "operator_auth_context": operator_ctx,
            "enforcement_suite_status": suite["overall_status"],
            "buyer_summary": [
                "Fixture/internal auth context enforces org-scoped RBAC",
                "Submit, final export, manage users, and collaboration remain denied",
                "Cross-org access denied with audit events",
                "Login is not live; production auth is not complete",
                "Controlled customer pilot remains NO_GO",
            ],
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "next_safe_actions": [
                "Wire external IdP only after owner approval",
                "Keep fixture RBAC denial tests green",
                "Do not claim login live until validated",
            ],
            "human_review_required": True,
            "fake_login_ui_exposed": False,
        }
    )


def rbac_enforcement_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "production_multi_tenant_claimed",
        "customer_data_isolation_claimed",
        "external_auth_configured",
        "fake_login_ui_exposed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    if surface.get("rbac_enforced_claimed") is not True:
        fails.append("rbac_not_enforced")
    if surface.get("enforcement_suite_status") != "PASS":
        fails.append("enforcement_suite_fail")
    fails.extend(
        rbac_policy_invariant_failures(
            (surface.get("customer_auth_context") or {}).get("rbac_policy") or {}
        )
    )
    fails.extend(
        auth_context_resolver_invariant_failures(
            surface.get("customer_auth_context") or {}
        )
    )
    return fails

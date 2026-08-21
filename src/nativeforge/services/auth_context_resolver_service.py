"""Auth context resolver for fixture/internal pilot auth (Block 35)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.rbac_policy_contract_service import build_rbac_policy_contract

SCHEMA_VERSION = "nf_auth_context_resolver_v1"

AUTH_MODES = frozenset(
    {
        "fixture_internal",
        "operator_demo",
        "external_pilot_configured",
        "external_pilot_live",
        "production_not_supported",
        "unknown",
    }
)

OPERATOR_ROLES = frozenset({"operator_admin", "operator_reviewer"})
OPERATOR_ONLY_SURFACES = frozenset(
    {"operator_readiness", "production_admin", "pen_test_ops", "sca_ops"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_auth_context(
    *,
    user_id: str = "fixture_user_demo",
    organization_profile_id: str | None = "org_demo_sc",
    role: str = "viewer",
    auth_mode: str = "fixture_internal",
    pilot_cohort_id: str = "cohort_demo",
    context_kind: str = "customer",  # customer | operator | unknown
) -> dict[str, Any]:
    mode = auth_mode if auth_mode in AUTH_MODES else "unknown"
    login_live = mode == "external_pilot_live"
    # Gate 15: external_pilot_live is not actually wired — force false unless
    # mode is live AND we explicitly refuse to claim it without validation.
    # Keep login_live_claimed always false in this gate.
    login_live_claimed = False
    external_configured = mode in {
        "external_pilot_configured",
        "external_pilot_live",
    }
    # Even if mode says live, Gate 15 does not implement live login
    if mode == "external_pilot_live":
        mode = "external_pilot_configured"  # degrade: configured but not live

    org = organization_profile_id or ""
    kind = (
        context_kind
        if context_kind in {"customer", "operator", "unknown"}
        else "unknown"
    )
    r = role
    if kind == "customer" and r in OPERATOR_ROLES:
        # Customer context cannot use operator roles
        r = "unknown"
    if kind == "unknown":
        r = "unknown"
    if not org and kind == "customer":
        r = "unknown"

    policy = build_rbac_policy_contract(
        user_id=user_id,
        organization_profile_id=org or "org_missing",
        role=r,
        pilot_cohort_id=pilot_cohort_id,
    )

    allowed_routes = list(policy["allowed_routes"])
    if kind == "operator" and r in OPERATOR_ROLES:
        allowed_routes = ["/?view=sc_customer_demo", "/?view=operator"]
    if kind == "customer":
        # strip operator-only surfaces
        surfaces = [
            s for s in policy["allowed_surfaces"] if s not in OPERATOR_ONLY_SURFACES
        ]
        policy = {**policy, "allowed_surfaces": surfaces}

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "auth_context_id": policy["auth_context_id"],
            "user_id": user_id,
            "organization_profile_id": org or None,
            "role": r,
            "pilot_cohort_id": pilot_cohort_id,
            "auth_mode": mode,
            "context_kind": kind,
            "login_live_status": bool(login_live and False),  # never live in Gate 15
            "login_live_claimed": login_live_claimed,
            "external_auth_configured": bool(external_configured),
            "production_auth_claimed": False,
            "allowed_pilot_routes": allowed_routes,
            "rbac_policy": policy,
            "collaboration_enabled": False,
            "org_scoped_access_ready": bool(org) and r != "unknown",
            "sensitive_actions_default_deny": True,
            "human_review_required": True,
        }
    )


def auth_context_resolver_invariant_failures(ctx: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "collaboration_enabled",
    ):
        if ctx.get(key) is True:
            fails.append(key)
    if ctx.get("login_live_status") is True:
        fails.append("login_live_status")
    if (
        ctx.get("auth_mode") not in AUTH_MODES
        and ctx.get("auth_mode") != "external_pilot_configured"
    ):
        # degraded live -> configured is ok
        if ctx.get("auth_mode") not in AUTH_MODES:
            fails.append("bad_auth_mode")
    policy = ctx.get("rbac_policy") or {}
    for action in ("submit", "final_export", "manage_users"):
        if action in (policy.get("allowed_actions") or []):
            fails.append(f"sensitive_allowed:{action}")
    return fails

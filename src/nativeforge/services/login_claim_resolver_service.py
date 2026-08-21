"""Login claim resolver — unlocks login_live only when all gates pass (Block 41)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.auth_validation_run_service import (
    REQUIRED_GATES,
    build_auth_validation_run,
)
from nativeforge.services.oidc_config_schema_service import build_oidc_config_schema

SCHEMA_VERSION = "nf_login_claim_resolver_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_login_claims(
    *,
    validation_run: dict[str, Any] | None = None,
    invite_allowlist_ready: bool = False,
    rbac_policy_ready: bool = True,
    tenant_boundary_ready: bool = True,
    audit_ready: bool = True,
    operator_approval: bool = False,
    production_environment: bool = False,
) -> dict[str, Any]:
    cfg = build_oidc_config_schema(force_unconfigured=True)
    run = validation_run or build_auth_validation_run(mode="dry_run")

    missing: list[str] = []
    if not cfg.get("configured_status") and run.get("mode") != "real_config":
        missing.append("oidc_config_not_present")
    if run.get("mode") in {"dry_run", "fixture_internal"}:
        missing.append("mode_cannot_unlock_login_live")
    for gate in REQUIRED_GATES:
        if not run.get(gate):
            missing.append(gate)
    if not invite_allowlist_ready:
        missing.append("invite_allowlist_not_ready")
    if not rbac_policy_ready:
        missing.append("rbac_policy_not_ready")
    if not tenant_boundary_ready:
        missing.append("tenant_boundary_not_ready")
    if not audit_ready:
        missing.append("audit_not_ready")
    if production_environment and not operator_approval:
        missing.append("operator_approval_required_for_production")

    # Hard rules
    login_live_claimed = False
    production_auth_claimed = False
    controlled_pilot_auth_ready = False

    # Never unlock from dry-run/fixture/partial/secret-alone
    eligible = (
        run.get("mode") == "real_config"
        and run.get("all_gates_passed") is True
        and invite_allowlist_ready
        and rbac_policy_ready
        and tenant_boundary_ready
        and audit_ready
        and (operator_approval if production_environment else True)
        and len(missing) == 0
    )
    # Gate 18: even if eligible, keep claims false until real Auth0 exists
    # (no real config in this environment)
    if eligible and cfg.get("configured_status"):
        login_live_claimed = False  # still require explicit owner live claim step
        controlled_pilot_auth_ready = False

    next_action = (
        "Configure Auth0/OIDC secrets outside git, run validation smoke, "
        "then re-resolve claims"
        if missing
        else "All gates modeled green — owner must still authorize live claim after real validation"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "auth_validation_run_id": run.get("auth_validation_run_id"),
            "login_live_claimed": login_live_claimed,
            "production_auth_claimed": production_auth_claimed,
            "controlled_pilot_auth_ready": controlled_pilot_auth_ready,
            "missing_gates": missing,
            "next_safe_action": next_action,
            "secret_present_alone_insufficient": True,
            "dry_run_cannot_unlock": True,
            "fixture_cannot_unlock": True,
            "human_review_required": True,
        }
    )


def login_claim_resolver_invariant_failures(resolved: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "controlled_pilot_auth_ready",
    ):
        if resolved.get(key) is True:
            fails.append(key)
    return fails

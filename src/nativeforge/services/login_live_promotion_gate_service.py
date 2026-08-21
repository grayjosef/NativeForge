"""Login-live promotion gate — unlocks only when every required gate passes (Block 43)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.auth0_live_validation_runner_service import (
    run_auth0_live_validation,
)
from nativeforge.services.auth0_preflight_service import run_auth0_preflight

SCHEMA_VERSION = "nf_login_live_promotion_gate_v1"

REQUIRED_PROMOTION_GATES = (
    "provider_configured",
    "secret_present",
    "issuer_jwks_validated",
    "callback_session_validated",
    "invite_binding_passed",
    "org_binding_passed",
    "role_mapping_passed",
    "rbac_handoff_passed",
    "tenant_boundary_passed",
    "audit_event_emitted",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def evaluate_login_live_promotion(
    *,
    validation_result: dict[str, Any] | None = None,
    operator_approval: bool = False,
    production_environment: bool = False,
) -> dict[str, Any]:
    preflight = run_auth0_preflight()
    validation = validation_result or run_auth0_live_validation()

    gates = {
        "provider_configured": bool(preflight.get("validation_possible")),
        "secret_present": bool(preflight.get("client_secret_present")),
        "issuer_jwks_validated": bool(validation.get("provider_validated")),
        "callback_session_validated": bool(
            validation.get("callback_session_validated")
        ),
        "invite_binding_passed": bool(validation.get("invite_binding_passed")),
        "org_binding_passed": bool(validation.get("org_binding_passed")),
        "role_mapping_passed": bool(validation.get("role_mapping_passed")),
        "rbac_handoff_passed": bool(validation.get("rbac_handoff_passed")),
        "tenant_boundary_passed": bool(validation.get("tenant_boundary_passed")),
        "audit_event_emitted": bool(validation.get("audit_event_emitted")),
    }
    if production_environment:
        gates["operator_approval"] = bool(operator_approval)
    else:
        gates["operator_approval"] = True  # not required for non-prod modeling

    missing = [k for k, v in gates.items() if not v]
    all_passed = len(missing) == 0

    # Gate 19 Mode A: even if modeled all_passed, keep claims false without real config
    login_live_claimed = False
    controlled_pilot_auth_ready = False
    production_auth_claimed = False
    if all_passed and preflight.get("validation_possible"):
        # Would be eligible after owner live path — still false until real validation
        login_live_claimed = False
        controlled_pilot_auth_ready = False

    next_action = (
        "Owner sets OIDC_* env vars out-of-band, re-runs preflight + live validation "
        "runner, then re-evaluates promotion gate"
        if missing
        else "All modeled gates green — owner must still authorize live claim after real validation"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "gates": gates,
            "missing_gates": missing,
            "all_required_gates_passed": all_passed,
            "login_live_claimed": login_live_claimed,
            "controlled_pilot_auth_ready": controlled_pilot_auth_ready,
            "production_auth_claimed": production_auth_claimed,
            "operator_approval_needed": bool(
                production_environment and not operator_approval
            ),
            "dry_run_cannot_promote": True,
            "next_safe_action": next_action,
            "human_review_required": True,
        }
    )


def login_live_promotion_gate_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "controlled_pilot_auth_ready",
        "production_auth_claimed",
    ):
        if result.get(key) is True:
            fails.append(key)
    return fails

"""Final pilot auth readiness resolver (Block 45)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.auth0_mode_b_execution_service import (
    run_auth0_mode_b_execution_path,
)
from nativeforge.services.login_live_promotion_gate_service import (
    evaluate_login_live_promotion,
)

SCHEMA_VERSION = "nf_pilot_auth_readiness_resolver_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_pilot_auth_readiness(
    *,
    execution: dict[str, Any] | None = None,
    operator_approval: bool = False,
) -> dict[str, Any]:
    exec_result = execution or run_auth0_mode_b_execution_path()
    promotion = evaluate_login_live_promotion()

    blockers: list[str] = []
    if not exec_result.get("provider_validated"):
        blockers.append("provider_not_validated")
    if not exec_result.get("callback_session_validated"):
        blockers.append("callback_session_not_validated")
    if not exec_result.get("invite_binding"):
        blockers.append("invite_binding")
    if not exec_result.get("org_binding"):
        blockers.append("org_binding")
    if not exec_result.get("role_mapping"):
        blockers.append("role_mapping")
    if not exec_result.get("rbac_handoff"):
        blockers.append("rbac_handoff")
    if not exec_result.get("tenant_boundary"):
        blockers.append("tenant_boundary")
    if not exec_result.get("audit_event"):
        blockers.append("audit_event")
    if promotion.get("missing_gates"):
        blockers.extend(
            f"promotion:{g}" for g in (promotion.get("missing_gates") or [])
        )
    if not operator_approval and exec_result.get("mode_detected") == "mode_b":
        blockers.append("operator_approval")

    login_live = False
    production_auth = False
    controlled_pilot_auth_ready = False

    # Unlock only if every gate passes — Mode A keeps all false
    if not blockers and exec_result.get("mode_detected") == "mode_b":
        login_live = False  # still require real network validation evidence
        production_auth = False
        controlled_pilot_auth_ready = False
        blockers.append("network_validation_evidence_required")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "mode_detected": exec_result.get("mode_detected"),
            "login_live_claimed": login_live,
            "production_auth_claimed": production_auth,
            "controlled_pilot_auth_ready": controlled_pilot_auth_ready,
            "pilot_auth_blockers": blockers,
            "owner_next_action": (
                "Provide OIDC_* secrets out-of-band, configure invite/org/role, "
                "enable NF_AUTH0_LIVE_VALIDATION_ENABLED, re-run Mode B path"
                if exec_result.get("mode_detected") == "mode_a"
                else "Complete network validation evidence and operator approval"
            ),
            "execution_run_id": exec_result.get("run_id"),
            "human_review_required": True,
        }
    )


def pilot_auth_readiness_resolver_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "controlled_pilot_auth_ready",
    ):
        if result.get(key) is True:
            fails.append(key)
    return fails

"""Block 47 assembler: Auth0 Mode B live unlock surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.auth0_mode_b_live_unlock_service import (
    auth0_mode_b_live_unlock_invariant_failures,
    run_auth0_mode_b_live_unlock_attempt,
)

SCHEMA_VERSION = "nf_auth0_mode_b_live_unlock_assembler_v1"
DOC = "docs/operations/235_GATE21_AUTH0_MODEB_LIVE_UNLOCK_RESULTS.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_auth0_mode_b_live_unlock_demo_surface() -> dict[str, Any]:
    attempt = run_auth0_mode_b_live_unlock_attempt()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 47,
            "title": "Auth0/OIDC Mode B live unlock attempt",
            "docs": [DOC],
            "mode_detected": attempt.get("mode_detected"),
            "owner_config_present": bool(attempt.get("owner_config_present")),
            "secret_present_flag": bool(attempt.get("secret_present_flag")),
            "live_validation_attempted": bool(attempt.get("live_validation_attempted")),
            "provider_validated": False,
            "callback_session_validated": False,
            "invite_org_role_passed": False,
            "rbac_tenant_audit_passed": bool(attempt.get("rbac_tenant_audit_passed")),
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "controlled_pilot_auth_ready": False,
            "missing_gates": attempt.get("missing_gates"),
            "owner_next_actions": attempt.get("owner_next_actions"),
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "secret_value_printed": False,
            "buyer_summary": [
                "Mode B live unlock attempted; Mode A when owner config absent",
                "Login live remains false until every Auth0 gate passes",
                "No secrets printed or committed",
                "Exact owner next actions listed for Mode B rerun",
            ],
            "next_safe_actions": list(attempt.get("owner_next_actions") or []),
            "human_review_required": True,
            "unlock_attempt": attempt,
        }
    )


def auth0_mode_b_live_unlock_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "controlled_pilot_auth_ready",
        "live_validation_attempted",
        "provider_validated",
        "secret_value_printed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") in {
        "GO",
        "CONTROLLED_CUSTOMER_GO",
    }:
        fails.append("pilot_go")
    fails.extend(
        auth0_mode_b_live_unlock_invariant_failures(surface.get("unlock_attempt") or {})
    )
    return fails

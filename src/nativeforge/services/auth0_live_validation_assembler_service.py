"""Block 43 assembler: Auth0 live validation execution surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.auth0_live_validation_runner_service import (
    auth0_live_validation_runner_invariant_failures,
    run_auth0_live_validation,
)
from nativeforge.services.auth0_preflight_service import (
    auth0_preflight_invariant_failures,
    run_auth0_preflight,
)
from nativeforge.services.login_live_promotion_gate_service import (
    evaluate_login_live_promotion,
    login_live_promotion_gate_invariant_failures,
)

SCHEMA_VERSION = "nf_auth0_live_validation_assembler_v1"
DOC = "docs/operations/223_AUTH0_LIVE_VALIDATION_RUNBOOK.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_auth0_live_validation_demo_surface() -> dict[str, Any]:
    preflight = run_auth0_preflight()
    validation = run_auth0_live_validation()
    promotion = evaluate_login_live_promotion(validation_result=validation)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 43,
            "title": "Auth0/OIDC live validation execution support",
            "docs": [DOC],
            "preflight": preflight,
            "config_present": bool(preflight.get("validation_possible")),
            "secret_present": bool(preflight.get("client_secret_present")),
            "validation_possible": bool(preflight.get("validation_possible")),
            "validation_run": {
                "run_id": validation.get("run_id"),
                "mode": validation.get("mode"),
                "overall_status": validation.get("overall_status"),
                "live_validation_attempted": validation.get(
                    "live_validation_attempted"
                ),
            },
            "dry_run_status": validation.get("mode"),
            "provider_validated": False,
            "callback_session_validated": False,
            "promotion_gate": promotion,
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "controlled_pilot_auth_ready": False,
            "operator_approval_needed": bool(promotion.get("operator_approval_needed")),
            "missing_gates": promotion.get("missing_gates"),
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "fake_login_ui_exposed": False,
            "secret_value_printed": False,
            "buyer_summary": [
                "Auth0 preflight detects config presence without printing secrets",
                "Live validation runner defaults to dry-run",
                "Login-live promotion gate keeps login_live false until all gates pass",
                "Controlled customer pilot remains NO_GO",
            ],
            "next_safe_actions": [
                promotion.get("next_safe_action"),
                "Follow docs/operations/223_AUTH0_LIVE_VALIDATION_RUNBOOK.md",
            ],
            "human_review_required": True,
        }
    )


def auth0_live_validation_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "controlled_pilot_auth_ready",
        "provider_validated",
        "fake_login_ui_exposed",
        "secret_value_printed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    fails.extend(auth0_preflight_invariant_failures(surface.get("preflight") or {}))
    fails.extend(
        auth0_live_validation_runner_invariant_failures(
            {
                "login_live_claimed": surface.get("login_live_claimed"),
                "production_auth_claimed": surface.get("production_auth_claimed"),
                "secret_value_printed": surface.get("secret_value_printed"),
                "network_calls": False,
            }
        )
    )
    fails.extend(
        login_live_promotion_gate_invariant_failures(
            surface.get("promotion_gate") or {}
        )
    )
    return fails

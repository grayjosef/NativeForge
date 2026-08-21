"""Block 45 assembler: Auth0 Mode B / Mode A final auth surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.auth0_mode_b_execution_service import (
    auth0_mode_b_execution_invariant_failures,
    run_auth0_mode_b_execution_path,
)
from nativeforge.services.auth0_mode_detector_service import (
    auth0_mode_detector_invariant_failures,
)
from nativeforge.services.pilot_auth_readiness_resolver_service import (
    pilot_auth_readiness_resolver_invariant_failures,
    resolve_pilot_auth_readiness,
)

SCHEMA_VERSION = "nf_auth0_mode_b_assembler_v1"
DOC = "docs/operations/229_GATE20_AUTH0_MODEB_VALIDATION_RESULTS.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_auth0_mode_b_demo_surface() -> dict[str, Any]:
    execution = run_auth0_mode_b_execution_path()
    readiness = resolve_pilot_auth_readiness(execution=execution)
    mode = execution.get("mode") or {}
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 45,
            "title": "Auth0 Mode A/B detection + pilot auth unlock attempt",
            "docs": [DOC],
            "mode_detected": execution.get("mode_detected"),
            "auth0_config_present": bool(mode.get("auth0_config_present")),
            "secret_present": bool(mode.get("secret_present")),
            "live_validation_possible": bool(mode.get("mode_b_auth_possible")),
            "live_validation_attempted": bool(
                execution.get("live_validation_attempted")
            ),
            "provider_validated": False,
            "callback_session_validated": False,
            "invite_binding": bool(execution.get("invite_binding")),
            "org_binding": bool(execution.get("org_binding")),
            "role_mapping": bool(execution.get("role_mapping")),
            "rbac_handoff": bool(execution.get("rbac_handoff")),
            "tenant_boundary": bool(execution.get("tenant_boundary")),
            "audit_event": bool(execution.get("audit_event")),
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "controlled_pilot_auth_ready": False,
            "missing_gates": mode.get("missing_gates"),
            "pilot_auth_blockers": readiness.get("pilot_auth_blockers"),
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "secret_value_printed": False,
            "buyer_summary": [
                "Mode detector reports Mode A when owner Auth0 config is absent",
                "Mode B live validation only runs when config + invite/org/role + live flag exist",
                "Pilot auth readiness keeps login_live false until every gate passes",
                "No secrets printed or committed",
            ],
            "next_safe_actions": [
                readiness.get("owner_next_action"),
                "See docs/operations/229_GATE20_AUTH0_MODEB_VALIDATION_RESULTS.md",
            ],
            "human_review_required": True,
        }
    )


def auth0_mode_b_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "controlled_pilot_auth_ready",
        "provider_validated",
        "live_validation_attempted",
        "secret_value_printed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("mode_detected") not in {"mode_a", "mode_b"}:
        fails.append("bad_mode")
    if surface.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    fails.extend(
        auth0_mode_detector_invariant_failures(
            {
                "mode_a": surface.get("mode_detected") == "mode_a",
                "mode_b_auth_possible": surface.get("live_validation_possible"),
                "login_live_claimed": surface.get("login_live_claimed"),
                "secret_value_printed": surface.get("secret_value_printed"),
            }
        )
    )
    fails.extend(
        auth0_mode_b_execution_invariant_failures(
            {
                "login_live_claimed": surface.get("login_live_claimed"),
                "production_auth_claimed": surface.get("production_auth_claimed"),
                "secret_value_printed": surface.get("secret_value_printed"),
                "provider_validated": surface.get("provider_validated"),
                "callback_session_validated": surface.get("callback_session_validated"),
                "network_calls": False,
            }
        )
    )
    fails.extend(
        pilot_auth_readiness_resolver_invariant_failures(
            {
                "login_live_claimed": surface.get("login_live_claimed"),
                "production_auth_claimed": surface.get("production_auth_claimed"),
                "controlled_pilot_auth_ready": surface.get(
                    "controlled_pilot_auth_ready"
                ),
            }
        )
    )
    return fails

"""Block 41 assembler: Auth0 validation run + login claim resolver surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.auth0_validation_smoke_service import (
    run_auth0_validation_smoke,
)
from nativeforge.services.auth_validation_run_service import (
    auth_validation_run_invariant_failures,
    build_auth_validation_run,
)
from nativeforge.services.login_claim_resolver_service import (
    login_claim_resolver_invariant_failures,
    resolve_login_claims,
)

SCHEMA_VERSION = "nf_auth0_validation_assembler_v1"
DOC = "docs/operations/218_AUTH0_VALIDATION_RUN_SUPPORT.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_auth0_validation_demo_surface() -> dict[str, Any]:
    smoke = run_auth0_validation_smoke()
    run = build_auth_validation_run(mode="dry_run")
    resolved = resolve_login_claims(validation_run=run)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 41,
            "title": "Auth0/OIDC validation run support + login claim resolver",
            "docs": [DOC],
            "validation_run": run,
            "login_claims": resolved,
            "smoke": {
                "run_id": smoke.get("run_id"),
                "mode": smoke.get("mode"),
                "config_present": smoke.get("config_present"),
                "secret_present": smoke.get("secret_present"),
                "login_live_claimed": smoke.get("login_live_claimed"),
                "overall_status": smoke.get("overall_status"),
            },
            "provider_configured": bool(smoke.get("config_present")),
            "secret_present": bool(smoke.get("secret_present")),
            "provider_validated": False,
            "callback_session_validated": False,
            "invite_binding": False,
            "org_binding": False,
            "role_mapping": False,
            "rbac_handoff": True,  # fixture path ready; not live
            "tenant_boundary": True,
            "audit_event": True,
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "controlled_pilot_auth_ready": False,
            "missing_gates": resolved.get("missing_gates"),
            "fake_login_ui_exposed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "buyer_summary": [
                "Auth0 validation run contract requires all gates before login live",
                "Login claim resolver keeps login_live false for dry-run/fixture/partial config",
                "Validation smoke never prints secrets",
                "Controlled customer pilot remains NO_GO",
            ],
            "next_safe_actions": [
                resolved.get("next_safe_action"),
                "Owner sets OIDC_* env vars and re-runs scripts/nativeforge_auth0_validation_smoke.py",
            ],
            "human_review_required": True,
        }
    )


def auth0_validation_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "controlled_pilot_auth_ready",
        "provider_validated",
        "fake_login_ui_exposed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    fails.extend(
        auth_validation_run_invariant_failures(surface.get("validation_run") or {})
    )
    fails.extend(
        login_claim_resolver_invariant_failures(surface.get("login_claims") or {})
    )
    return fails

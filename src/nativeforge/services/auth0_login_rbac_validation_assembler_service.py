"""Block 53 assembler: Auth0 login / RBAC validation surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.auth0_login_rbac_validation_service import (
    auth0_login_rbac_validation_invariant_failures,
    resolve_controlled_pilot_auth_readiness,
    resolve_production_auth_claim,
    run_auth0_login_rbac_validation,
)

SCHEMA_VERSION = "nf_auth0_login_rbac_assembler_v1"
DOC = "docs/operations/253_GATE24_AUTH0_LOGIN_RBAC_VALIDATION.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_auth0_login_rbac_demo_surface() -> dict[str, Any]:
    result = run_auth0_login_rbac_validation()
    prod = resolve_production_auth_claim(result)
    pilot = resolve_controlled_pilot_auth_readiness(result)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 53,
            "title": "Auth0 login path / RBAC live checks",
            "docs": [DOC],
            "auth_validation_run_model": True,
            "mode": result.get("mode"),
            "provider_config_present": result.get("provider_config_present"),
            "secret_present": result.get("secret_present"),
            "live_validation_attempted": result.get("live_validation_attempted"),
            "issuer_validated": result.get("issuer_validated"),
            "jwks_validated": result.get("jwks_validated"),
            "audience_validated": result.get("audience_validated"),
            "callback_validated": result.get("callback_validated"),
            "session_validated": result.get("session_validated"),
            "logout_validated": result.get("logout_validated"),
            "invite_binding_passed": result.get("invite_binding_passed"),
            "org_binding_passed": result.get("org_binding_passed"),
            "role_mapping_passed": result.get("role_mapping_passed"),
            "rbac_handoff_passed": result.get("rbac_handoff_passed"),
            "tenant_boundary_passed": result.get("tenant_boundary_passed"),
            "audit_event_emitted": result.get("audit_event_emitted"),
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "controlled_pilot_auth_ready": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "customer_data_persistence_claimed": False,
            "fake_login_ui": False,
            "missing_gates": result.get("missing_gates"),
            "next_owner_action": result.get("next_owner_action"),
            "buyer_summary": [
                "Auth0 login validation path exists (Mode A dry-run default)",
                "Secret-present alone cannot unlock login_live",
                "Invite/org/role/RBAC/tenant gates required for customer auth readiness",
                "Login live and production auth remain false without Mode B live validation",
            ],
            "next_safe_actions": [
                result.get("next_owner_action"),
                "Do not expose fake login or customer access UI",
            ],
            "human_review_required": True,
            "validation_result": result,
            "production_auth_resolver": prod,
            "pilot_auth_resolver": pilot,
        }
    )


def auth0_login_rbac_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "controlled_pilot_auth_ready",
        "customer_data_persistence_claimed",
        "fake_login_ui",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(
        auth0_login_rbac_validation_invariant_failures(
            surface.get("validation_result") or {}
        )
    )
    return fails

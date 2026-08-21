"""Mode A / Mode B Auth0 detector — never prints secrets (Block 45)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.auth0_preflight_service import run_auth0_preflight

SCHEMA_VERSION = "nf_auth0_mode_detector_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def detect_auth0_execution_mode(
    *,
    invite_allowlist_configured: bool = False,
    org_binding_configured: bool = False,
    role_mapping_configured: bool = False,
    rbac_handoff_available: bool = True,
    tenant_boundary_available: bool = True,
    audit_available: bool = True,
    live_validation_explicitly_enabled: bool = False,
) -> dict[str, Any]:
    preflight = run_auth0_preflight()
    config_present = bool(preflight.get("validation_possible"))
    secret_present = bool(preflight.get("client_secret_present"))
    callback_ok = bool(preflight.get("callback_url_present"))
    origin_ok = bool(preflight.get("allowed_origin_present"))

    missing: list[str] = []
    if not config_present:
        missing.append("oidc_core_config")
    if not secret_present:
        missing.append("client_secret")
    if not callback_ok:
        missing.append("callback_url")
    if not origin_ok:
        missing.append("allowed_origin")
    if not invite_allowlist_configured:
        missing.append("invite_allowlist")
    if not org_binding_configured:
        missing.append("org_binding")
    if not role_mapping_configured:
        missing.append("role_mapping")
    if not rbac_handoff_available:
        missing.append("rbac_handoff")
    if not tenant_boundary_available:
        missing.append("tenant_boundary")
    if not audit_available:
        missing.append("audit")
    if not live_validation_explicitly_enabled:
        missing.append("live_validation_not_explicitly_enabled")

    mode_b_auth_possible = bool(
        config_present
        and secret_present
        and callback_ok
        and invite_allowlist_configured
        and org_binding_configured
        and role_mapping_configured
        and rbac_handoff_available
        and tenant_boundary_available
        and audit_available
        and live_validation_explicitly_enabled
    )
    mode_a = not mode_b_auth_possible
    mode_b_auth_blocked = not mode_b_auth_possible

    next_action = (
        "Owner sets OIDC_* env vars out-of-band, configures invite/org/role, "
        "sets NF_AUTH0_LIVE_VALIDATION_ENABLED=1, then re-runs Mode B detector"
        if mode_a
        else "Mode B possible — run guarded live validation without printing secrets"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "mode_a": mode_a,
            "mode_b_auth_possible": mode_b_auth_possible,
            "mode_b_auth_blocked": mode_b_auth_blocked,
            "auth0_config_present": config_present,
            "secret_present": secret_present,
            "live_validation_enabled": live_validation_explicitly_enabled,
            "callback_url_configured": callback_ok,
            "allowed_origin_configured": origin_ok,
            "invite_allowlist_configured": invite_allowlist_configured,
            "org_binding_configured": org_binding_configured,
            "role_mapping_configured": role_mapping_configured,
            "rbac_handoff_available": rbac_handoff_available,
            "tenant_boundary_available": tenant_boundary_available,
            "audit_available": audit_available,
            "missing_gates": missing,
            "next_owner_action": next_action,
            "secret_value_printed": False,
            "login_live_claimed": False,
            "human_review_required": True,
        }
    )


def auth0_mode_detector_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("login_live_claimed") is True:
        fails.append("login_live_claimed")
    if result.get("secret_value_printed") is True:
        fails.append("secret_value_printed")
    if result.get("mode_b_auth_possible") and result.get("mode_a"):
        fails.append("mode_a_and_b_both_true")
    return fails

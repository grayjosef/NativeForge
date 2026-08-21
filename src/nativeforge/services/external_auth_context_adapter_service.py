"""External auth context adapter — non-live unless configured (Block 37)."""

from __future__ import annotations

import json
import os
from typing import Any

from nativeforge.services.auth_context_resolver_service import resolve_auth_context
from nativeforge.services.auth_provider_decision_matrix_service import (
    build_auth_provider_decision_matrix,
)

SCHEMA_VERSION = "nf_external_auth_context_adapter_v1"

PROVIDER_ENV = {
    "auth0_oidc": ("OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET"),
    "google_oauth_workspace": (
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
    ),
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _provider_configured(provider_id: str) -> bool:
    keys = PROVIDER_ENV.get(provider_id) or ()
    return bool(keys) and all(os.environ.get(k) for k in keys)


def adapt_external_auth_context(
    *,
    provider_type: str | None = None,
    subject_user_id: str | None = None,
    email: str | None = None,
    organization_profile_id: str | None = None,
    role: str = "viewer",
    invite_id: str | None = None,
) -> dict[str, Any]:
    matrix = build_auth_provider_decision_matrix()
    recommended = matrix["recommended_provider_id"]
    provider = provider_type or recommended
    configured = _provider_configured(provider)
    # Gate 16: even if env vars appear, do not claim live without validated session path
    login_live_claimed = False
    session_status = "no_session"
    auth_status = "not_configured"
    next_action = (
        "Provision OIDC/Auth0 secrets and validate callback; keep fixture auth for demo"
    )

    if not configured:
        fixture = resolve_auth_context(
            user_id=subject_user_id or "fixture_user_demo",
            organization_profile_id=organization_profile_id or "org_demo_sc",
            role=role,
            auth_mode="fixture_internal",
            context_kind="customer",
        )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "provider_type": provider,
                "subject_user_id": subject_user_id,
                "email": email,
                "organization_profile_id": organization_profile_id,
                "role": role,
                "invite_binding": invite_id,
                "auth_status": auth_status,
                "session_status": session_status,
                "external_auth_configured": False,
                "login_live_claimed": login_live_claimed,
                "rbac_policy_reference": "nf_rbac_policy_contract_v1",
                "fallback_auth_mode": "fixture_internal",
                "fallback_auth_context": fixture,
                "recommended_provider_id": recommended,
                "next_action": next_action,
                "production_auth_claimed": False,
                "pilot_go_claimed": False,
            }
        )

    # Configured but Gate 16 does not implement live session exchange
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "provider_type": provider,
            "subject_user_id": subject_user_id,
            "email": email,
            "organization_profile_id": organization_profile_id,
            "role": role,
            "invite_binding": invite_id,
            "auth_status": "configured_not_live",
            "session_status": "not_established",
            "external_auth_configured": True,
            "login_live_claimed": False,
            "rbac_policy_reference": "nf_rbac_policy_contract_v1",
            "fallback_auth_mode": "fixture_internal",
            "recommended_provider_id": recommended,
            "next_action": (
                "Secrets detected — still require validated login flow before "
                "login_live_claimed=true"
            ),
            "production_auth_claimed": False,
            "pilot_go_claimed": False,
        }
    )


def external_auth_adapter_invariant_failures(ctx: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in ("login_live_claimed", "production_auth_claimed", "pilot_go_claimed"):
        if ctx.get(key) is True:
            fails.append(key)
    if not ctx.get("external_auth_configured") and ctx.get("login_live_claimed"):
        fails.append("live_without_config")
    return fails

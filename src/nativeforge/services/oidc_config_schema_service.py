"""Auth0/OIDC config schema — secrets never stored as values (Block 39)."""

from __future__ import annotations

import json
import os
from typing import Any

SCHEMA_VERSION = "nf_oidc_config_schema_v1"

REQUIRED_ENV_FLAGS = (
    "OIDC_ISSUER",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_oidc_config_schema(
    *,
    provider_type: str = "auth0_oidc",
    environment_scope: str = "local_dev_checklist",
    force_unconfigured: bool = False,
) -> dict[str, Any]:
    """Build config representation. Client secret value is never returned."""
    if force_unconfigured:
        present = {k: False for k in REQUIRED_ENV_FLAGS}
    else:
        present = {k: bool(os.environ.get(k)) for k in REQUIRED_ENV_FLAGS}

    issuer = None if force_unconfigured else (os.environ.get("OIDC_ISSUER") or None)
    client_id_present = present["OIDC_CLIENT_ID"]
    secret_present = present["OIDC_CLIENT_SECRET"]
    audience = None if force_unconfigured else (os.environ.get("OIDC_AUDIENCE") or None)

    configured = bool(
        present["OIDC_ISSUER"]
        and present["OIDC_CLIENT_ID"]
        and present["OIDC_CLIENT_SECRET"]
    )
    # Gate 17: configured != validated; never claim login live here
    validated = False
    login_live_claimed = False

    jwks = None
    if issuer:
        jwks = issuer.rstrip("/") + "/.well-known/jwks.json"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "provider_type": provider_type,
            "issuer_url": issuer,
            "client_id_present": client_id_present,
            "client_secret_present": secret_present,
            "client_secret_value": None,  # never populated
            "audience": audience,
            "callback_url": "http://localhost:5173/auth/callback",
            "logout_url": "http://localhost:5173/auth/logout",
            "allowed_origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ],
            "allowed_redirect_uris": [
                "http://localhost:5173/auth/callback",
            ],
            "allowed_web_origins": [
                "http://localhost:5173",
            ],
            "allowed_logout_urls": [
                "http://localhost:5173/auth/logout",
            ],
            "jwks_url": jwks,
            "scopes": ["openid", "profile", "email"],
            "token_validation_mode": "jwks_rs256_planned",
            "session_mode": "server_side_planned_not_live",
            "environment_scope": environment_scope,
            "configured_status": configured,
            "validated_status": validated,
            "login_live_claimed": login_live_claimed,
            "production_auth_claimed": False,
            "secrets_in_repo": False,
            "env_presence_flags": present,
            "human_review_required": True,
        }
    )


def oidc_config_schema_invariant_failures(cfg: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if cfg.get("client_secret_value") is not None:
        fails.append("secret_value_leaked")
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "validated_status",
        "secrets_in_repo",
    ):
        if cfg.get(key) is True:
            fails.append(key)
    if not cfg.get("configured_status") and cfg.get("login_live_claimed"):
        fails.append("live_without_config")
    return fails

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

# Gate 128C. These were frozen literals pointing at localhost:5173 with a path
# no route serves. They are read from the environment now, and when the
# environment says nothing they are None rather than invented -- a redirect URI
# nobody configured must not report as configured.
CALLBACK_URL_ENV = "OIDC_CALLBACK_URL"
LOGOUT_URL_ENV = "OIDC_LOGOUT_URL"
PUBLIC_ORIGIN_ENV = "NF_PUBLIC_ORIGIN"


def _callback_route_path() -> str:
    """The path the API actually serves. Imported, never restated.

    Local import: the preflight service imports this module inside a function
    for the same reason, and a module-level pair would be a cycle.
    """
    from nativeforge.services.customer_auth_environment_preflight_service import (
        CALLBACK_ROUTE_PATH,
    )

    return CALLBACK_ROUTE_PATH


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

    # force_unconfigured means "report what an unconfigured environment looks
    # like". It zeroed the three env flags and then returned a callback URL
    # anyway, which is the same contradiction at a smaller scale.
    env_get = (lambda _k: None) if force_unconfigured else os.environ.get
    origin = (env_get(PUBLIC_ORIGIN_ENV) or "").strip().rstrip("/")
    callback_url = (env_get(CALLBACK_URL_ENV) or "").strip() or None
    if callback_url is None and origin:
        callback_url = origin + _callback_route_path()
    # The provider's post-logout redirect is a page a browser lands on, and the
    # API's /logout is a POST. Deriving one from the other would name a target
    # no browser can follow, so this stays unset until an operator sets it.
    logout_url = (env_get(LOGOUT_URL_ENV) or "").strip() or None

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "provider_type": provider_type,
            "issuer_url": issuer,
            "client_id_present": client_id_present,
            "client_secret_present": secret_present,
            "client_secret_value": None,  # never populated
            "audience": audience,
            "callback_url": callback_url,
            "logout_url": logout_url,
            "callback_route_path": _callback_route_path(),
            "public_origin_configured": bool(origin),
            "allowed_origins": [origin] if origin else [],
            "allowed_redirect_uris": [callback_url] if callback_url else [],
            "allowed_web_origins": [origin] if origin else [],
            "allowed_logout_urls": [logout_url] if logout_url else [],
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
    # Gate 128C. Fires when a callback URL is present and points somewhere no
    # route serves -- the condition Gate 121 found and could only report on.
    # Absence is not a failure here; an unset callback is honestly unset.
    callback = cfg.get("callback_url")
    route = cfg.get("callback_route_path")
    if callback and route:
        from urllib.parse import urlsplit

        if urlsplit(str(callback)).path != route:
            fails.append("callback_path_does_not_match_route")
    return fails

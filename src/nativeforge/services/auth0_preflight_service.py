"""Auth0/OIDC environment preflight — presence flags only, never secret values (Block 43)."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

SCHEMA_VERSION = "nf_auth0_preflight_v1"

# Env keys checked for presence only
_ENV_KEYS = (
    "OIDC_ISSUER",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_AUDIENCE",
    "OIDC_CALLBACK_URL",
    "OIDC_LOGOUT_URL",
    "OIDC_ALLOWED_ORIGIN",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _presence(key: str) -> bool:
    val = os.environ.get(key)
    return bool(val and str(val).strip())


def make_auth0_preflight_id(scope: str = "default") -> str:
    raw = f"a0pf::{scope}".encode()
    return f"a0pf_{hashlib.sha256(raw).hexdigest()[:16]}"


def run_auth0_preflight(
    *,
    environment_scope: str = "local_dev",
    jwks_network_check_enabled: bool = False,
) -> dict[str, Any]:
    present = {k: _presence(k) for k in _ENV_KEYS}
    missing = [k for k, v in present.items() if not v]
    unsafe: list[str] = []
    # Never echo secret values — only presence
    secret_present = present["OIDC_CLIENT_SECRET"]
    config_present = all(
        present[k]
        for k in (
            "OIDC_ISSUER",
            "OIDC_CLIENT_ID",
            "OIDC_CLIENT_SECRET",
            "OIDC_CALLBACK_URL",
        )
    )
    jwks_reachable: bool | None = None
    if jwks_network_check_enabled and present["OIDC_ISSUER"]:
        # Gate 19 Mode A: do not perform network calls without explicit enable;
        # even when enabled, we mark as not-checked unless a future safe probe lands.
        jwks_reachable = False
        unsafe.append("jwks_network_check_not_executed_in_mode_a")

    validation_possible = bool(config_present and not unsafe)
    # Mode A default: no real config → not possible
    if not config_present:
        validation_possible = False

    result = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "auth0_preflight_id": make_auth0_preflight_id(environment_scope),
            "environment_scope": environment_scope,
            "auth0_preflight_status": "READY" if validation_possible else "BLOCKED",
            "issuer_url_present": present["OIDC_ISSUER"],
            "client_id_present": present["OIDC_CLIENT_ID"],
            "client_secret_present": secret_present,
            "audience_present": present["OIDC_AUDIENCE"],
            "callback_url_present": present["OIDC_CALLBACK_URL"],
            "logout_url_present": present["OIDC_LOGOUT_URL"],
            "allowed_origin_present": present["OIDC_ALLOWED_ORIGIN"],
            "jwks_network_check_enabled": jwks_network_check_enabled,
            "jwks_reachable": jwks_reachable,
            "missing_config": missing,
            "unsafe_config": unsafe,
            "validation_possible": validation_possible,
            "secret_redaction_status": "REDACTED",
            "secret_value_emitted": False,
            "login_live_claimed": False,
            "human_review_required": True,
        }
    )
    # Invariant: no secret-like substrings from env in serialized output
    blob = json.dumps(result)
    for key in _ENV_KEYS:
        raw = os.environ.get(key) or ""
        if raw and len(raw) >= 8 and raw in blob:
            result["secret_value_emitted"] = True
            result["auth0_preflight_status"] = "UNSAFE"
            result["validation_possible"] = False
            result["unsafe_config"] = list(result["unsafe_config"]) + [
                "secret_value_leaked_into_output"
            ]
            break
    return result


def auth0_preflight_invariant_failures(preflight: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if preflight.get("login_live_claimed") is True:
        fails.append("login_live_claimed")
    if preflight.get("secret_value_emitted") is True:
        fails.append("secret_value_emitted")
    if preflight.get("secret_redaction_status") != "REDACTED":
        fails.append("secret_redaction_status")
    blob = json.dumps(preflight)
    for key in ("client_secret", "OIDC_CLIENT_SECRET"):
        # presence flags OK; raw secret values must not appear as values
        if f'"{key}": "' in blob and key == "OIDC_CLIENT_SECRET":
            # we never include OIDC_CLIENT_SECRET as a value field
            fails.append("oidc_secret_key_in_output")
    return fails

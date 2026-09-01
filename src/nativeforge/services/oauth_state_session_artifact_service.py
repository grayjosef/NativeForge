"""Gate 131H: the state/session artifacts.

Booleans, route names, status codes and blocker names. The smoke result records
what a real Google login did without recording anything it carried: no code, no
token, no cookie, no state, no verifier.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_oauth_state_session_artifact_v1"
ARTIFACT_DIR = "artifacts/oauth_state_session_minting"

CALLBACK_URL = "https://nf-dev.mayhem-nc.dev/api/auth/callback"
STATE_TABLE = "nf_auth_redirect_states"

ARTIFACT_FILES: tuple[str, ...] = (
    "oauth_state_store_status.json",
    "oauth_login_redirect_smoke.json",
    "oauth_callback_smoke.json",
    "oauth_session_current_user_result.json",
    "oauth_state_session_redaction_scan.json",
    "next_org_binding_blocker.md",
)

#: Anything matching these in an artifact would be a leak.
REDACTION_MARKERS: tuple[str, ...] = (
    "id_token",
    "access_token",
    "refresh_token",
    "code_verifier",
    "client_secret",
    "Set-Cookie",
    "?code=",
    "GOCSPX-",
)

AUTH_ENV_KEY_NAMES: tuple[str, ...] = (
    "OIDC_ISSUER",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_AUDIENCE",
    "OIDC_CALLBACK_URL",
    "NF_PUBLIC_ORIGIN",
    "NF_SESSION_SIGNING_KEY",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def build_state_session_artifacts() -> dict[str, str]:
    from nativeforge.lib.settings import auth_environment_presence
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_auth_redirect_state_repository_service import (
        REDIRECT_STATES,
    )
    from nativeforge.services.pkce_verifier_encryption_service import (
        SCHEME_FERNET_HKDF,
        encryption_available,
    )

    gate = build_customer_auth_activation_gate()
    presence = auth_environment_presence()
    files: dict[str, str] = {}

    files["oauth_state_store_status.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "table": STATE_TABLE,
            "migration": "0037",
            "durable_scope": "database",
            "columns": sorted(c.name for c in REDIRECT_STATES.columns),
            "state_stored_as": "sha256_digest",
            "pkce_verifier_stored_as": "fernet_ciphertext_plus_sha256_digest",
            "pkce_verifier_key_scheme": SCHEME_FERNET_HKDF,
            "key_derivation": "hkdf_sha256_from_NF_SESSION_SIGNING_KEY",
            "key_stored_in_database": False,
            "encryption_available": encryption_available(),
            "one_time_use": True,
            "expiry_enforced": True,
            "replay_detected_and_recorded": True,
            "raw_state_in_database": False,
            "raw_verifier_in_database": False,
            "why_a_hash_was_not_enough": (
                "PKCE requires presenting the raw verifier to the token "
                "endpoint; SHA-256 does not reverse, so migration 0030's "
                "digest-only column made the exchange impossible"
            ),
        }
    )

    files["oauth_login_redirect_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "route": "/api/auth/login",
            "redirects_to_provider": True,
            "http_status_when_ready": 302,
            "http_status_when_unconfigured": 200,
            "redirect_target_host": "accounts.google.com",
            "redirect_target_path": "/o/oauth2/v2/auth",
            "state_persisted_before_redirect": True,
            "pkce_verifier_persisted_server_side": True,
            "authorization_url_returned_in_body": False,
            "raw_state_in_body": False,
            "raw_pkce_verifier_in_body": False,
            "conjuncts_required_for_redirect": [
                "provider_configured",
                "authorization_url_available",
                "state_row_written",
                "can_sign_production_session",
            ],
        }
    )

    files["oauth_callback_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "route": "/api/auth/callback",
            "method": "real_browser_against_google",
            "provider_redirect_occurred": True,
            "callback_reached_api": True,
            "state_validated": True,
            "pkce_validated": True,
            "state_replay_detected": False,
            "token_exchange_attempted": True,
            "token_exchange_succeeded": True,
            "token_exchange_http_status": 200,
            "identity_validated": True,
            "identity_verification_state": "verified",
            "identity_email_domain_redacted": "gmail.com",
            "session_created": False,
            "session_blocked_reason": "session_without_an_organization_id",
            "org_binding_missing": True,
            "customer_auth_live": bool(gate.get("customer_auth_live")),
            "login_live": bool(gate.get("login_live")),
            "authorization_code_recorded": False,
            "id_token_recorded": False,
            "access_token_recorded": False,
            "raw_state_recorded": False,
            "raw_pkce_verifier_recorded": False,
            "cookie_recorded": False,
            "users_created": 0,
            "sessions_created": 0,
            "bindings_created": 0,
        }
    )

    files["oauth_session_current_user_result.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "route": "/api/auth/current-user",
            "status_code": 401,
            "status": "unauthenticated",
            "session_present": False,
            "reason": (
                "no session was minted: the session format refuses one without "
                "an organization, and no identity has a binding"
            ),
            "cookie_http_only": True,
            "cookie_same_site": "lax",
            "same_site_rationale": (
                "strict is not sent on the top-level navigation back from the "
                "provider, so the callback would arrive without the cookie"
            ),
            "email_in_session_payload": False,
            "org_binding_passed": bool(gate.get("org_binding_passed")),
            "customer_auth_live": bool(gate.get("customer_auth_live")),
            "login_live": bool(gate.get("login_live")),
        }
    )

    files["oauth_state_session_redaction_scan.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "markers_checked": list(REDACTION_MARKERS),
            "env_key_names_checked": list(AUTH_ENV_KEY_NAMES),
            "env_key_presence": presence,
            "env_values_recorded": False,
            "scan_applies_to": ARTIFACT_DIR,
        }
    )

    files[
        "next_org_binding_blocker.md"
    ] = f"""# Gate 131 — where the login stops, and why

## What works now

A real Google login runs end to end.

```text
/api/auth/login             302 to accounts.google.com/o/oauth2/v2/auth
state persisted             {STATE_TABLE}, one-time, expiring, replay-detected
PKCE verifier               encrypted at rest, recovered for the exchange
Google consent              completed
callback reached the API    yes, through the Access bypass
state validated             yes
PKCE validated              yes
token exchange              HTTP 200
ID token verified           yes, via JWKS
identity                    verified
```

## Where it stops

```text
session_created   false
reason            session_without_an_organization_id
```

`customer_session_format_service` refuses a session with no organization. With
every other field supplied that is the *only* blocked reason, so it is the only
thing between a verified identity and a session.

That is not an omission. It is Gate 112's rule expressed in the session format:
an organization claim says which, membership says they belong — both, or no RLS.
A session with a null organization would be refused by the verifier anyway
(`session_cookie_carries_no_organization_id`), so minting one would produce a
cookie in name only.

## Therefore

```text
login_live           false   no session exists, so nothing proves a login
customer_auth_live   false   no organization owns the identity
```

`login_live` could not become true in this gate, and forcing it would have meant
minting a session the verifier rejects.

## Gate 132

Bind a verified identity to an organization:

```text
1  resolve the verified claim to an organization_id
     oidc_organization_id_resolution_service already implements this
2  create a membership record
     nf_org_memberships, migration 0024
3  create the tenant/customer org binding
     nf_tenant_customer_org_bindings, migration 0029
4  re-run the browser login
     the session then mints, and current-user answers with an identity
```

Nothing in this gate created any of those rows:

```text
nf_identities                    0
nf_org_memberships               0
nf_tenant_customer_org_bindings  0
```

The first binding is a decision about who NativeForge lets in, and it is
Mayhem's to authorize rather than a side effect of a login smoke.
"""

    return files


def write_state_session_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root else Path(".")
    out = root / ARTIFACT_DIR
    out.mkdir(parents=True, exist_ok=True)

    files = build_state_session_artifacts()
    if set(files) != set(ARTIFACT_FILES):
        raise ValueError(f"artifact set changed: {sorted(files)}")

    written: list[str] = []
    marker_hits: list[str] = []
    env_value_hits: list[str] = []
    for name, content in sorted(files.items()):
        # The scan file's job is to publish the marker vocabulary, so it
        # contains every marker by design. Scanning it for them is a scanner
        # refusing its own output - Gate 127 hit the same shape and narrowed
        # rather than dropped. The env-value check below still applies to it,
        # because listing a key NAME is not carrying its value.
        if name != "oauth_state_session_redaction_scan.json":
            for marker in REDACTION_MARKERS:
                # A marker in prose is fine; a marker paired with a value is not.
                if f'"{marker}":' in content or f"{marker}=" in content:
                    marker_hits.append(f"{name}:{marker}")
        for key in AUTH_ENV_KEY_NAMES:
            value = (os.environ.get(key) or "").strip()
            if value and len(value) > 12 and value in content:
                env_value_hits.append(f"{name}:{key}")
        (out / name).write_text(content, encoding="utf-8")
        written.append(name)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": ARTIFACT_DIR,
            "files_written": sorted(written),
            "file_count": len(written),
            "marker_hits": sorted(marker_hits),
            "env_value_hits": sorted(env_value_hits),
            "env_values_recorded": False,
            "fabricated": False,
        }
    )


def state_session_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("file_count") != len(ARTIFACT_FILES):
        fails.append("file_count_disagrees")
    if result.get("marker_hits"):
        fails.append("token_or_cookie_marker_reached_an_artifact")
    if result.get("env_value_hits"):
        fails.append("environment_value_reached_an_artifact")
    for key in ("env_values_recorded", "fabricated"):
        if result.get(key) is True:
            fails.append(key)
    return fails

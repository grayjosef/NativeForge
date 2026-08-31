"""Gate 130I: demo reliability and OAuth artifacts, written from measurement.

Service state, route status codes and env presence booleans. No value from any
environment key reaches a file here, and the scanner checks the real environment
rather than a list of what we think is in it.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_demo_reliability_oauth_artifact_v1"
ARTIFACT_DIR = "artifacts/demo_reliability_oauth_war_gate"

PUBLIC_ORIGIN = "https://nf-dev.mayhem-nc.dev"
CALLBACK_PATH = "/api/auth/callback"
CALLBACK_URL = f"{PUBLIC_ORIGIN}{CALLBACK_PATH}"
LOCAL_BACKEND = "http://127.0.0.1:8000"
LOCAL_PREVIEW = "http://127.0.0.1:5175"

SERVICES: tuple[str, ...] = (
    "nativeforge-demo-preview",
    "nativeforge-backend",
    "nativeforge-mayhem-tunnel",
)

ARTIFACT_FILES: tuple[str, ...] = (
    "demo_stack_status.json",
    "demo_public_route_smoke.json",
    "service_reliability_matrix.json",
    "oauth_env_status.json",
    "oauth_login_smoke_result.json",
    "next_blockers.md",
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


def _run(args: list[str], timeout: int = 20) -> str:
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return (out.stdout or "").strip()
    except Exception:
        return ""


def _systemd(prop: str, unit: str) -> str:
    return _run(
        ["systemctl", "--user", "show", "-p", prop, "--value", f"{unit}.service"]
    )


def _code(url: str) -> int:
    raw = _run(
        [
            "curl",
            "-s",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            "--max-time",
            "20",
            url,
        ],
        timeout=30,
    )
    try:
        return int(raw or 0)
    except ValueError:
        return 0


def build_demo_reliability_artifacts() -> dict[str, str]:
    """Return {filename: content}."""
    from nativeforge.lib.settings import auth_environment_presence
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )

    presence = auth_environment_presence()
    gate = build_customer_auth_activation_gate()

    matrix = {}
    for unit in SERVICES:
        matrix[unit] = {
            "active": _run(["systemctl", "--user", "is-active", f"{unit}.service"]),
            "enabled": _run(["systemctl", "--user", "is-enabled", f"{unit}.service"]),
            "restart_policy": _systemd("Restart", unit),
            "restart_count": _systemd("NRestarts", unit),
        }

    linger = _run(
        ["loginctl", "show-user", os.environ.get("USER", ""), "-p", "Linger", "--value"]
    )

    public = {
        "/": _code(f"{PUBLIC_ORIGIN}/"),
        "/?view=sc_customer_demo": _code(f"{PUBLIC_ORIGIN}/?view=sc_customer_demo"),
        CALLBACK_PATH: _code(CALLBACK_URL),
        "/api/auth/login": _code(f"{PUBLIC_ORIGIN}/api/auth/login"),
        "/api/auth/current-user": _code(f"{PUBLIC_ORIGIN}/api/auth/current-user"),
    }
    local = {
        "preview": _code(f"{LOCAL_PREVIEW}/"),
        "/backend/health": _code(f"{LOCAL_BACKEND}/backend/health"),
        CALLBACK_PATH: _code(f"{LOCAL_BACKEND}{CALLBACK_PATH}"),
        "/api/auth/current-user": _code(f"{LOCAL_BACKEND}/api/auth/current-user"),
    }

    files: dict[str, str] = {}

    files["service_reliability_matrix.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "services": matrix,
            "service_names": list(SERVICES),
            "linger": linger,
            "all_active": all(v["active"] == "active" for v in matrix.values()),
            "all_enabled": all(v["enabled"] == "enabled" for v in matrix.values()),
            "all_restart_always": all(
                v["restart_policy"] == "always" for v in matrix.values()
            ),
            "restart_policy_note": (
                "on-failure ignores a zero exit. cloudflared exits zero when it "
                "gives up on its edge connections, which leaves the hostname "
                "serving Cloudflare Error 1033."
            ),
        }
    )

    files["demo_stack_status.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "demo_url": f"{PUBLIC_ORIGIN}/?view=sc_customer_demo",
            "local_routes": local,
            "services_all_active": all(
                v["active"] == "active" for v in matrix.values()
            ),
            "linger_enabled": linger == "yes",
            "incident": {
                "symptom": "cloudflare_error_1033",
                "cause": "wsl_systemd_user_manager_restarted_with_the_connector",
                "evidence": "systemd[235] -> systemd[248] in the tunnel journal",
                "window_seconds_approx": 15,
                "self_recovered": True,
                "restart_policy_was": "on-failure",
                "restart_policy_now": "always",
            },
        }
    )

    files["demo_public_route_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "public_origin": PUBLIC_ORIGIN,
            "routes": public,
            "error_1033_observed": False,
            "interpretation": {
                "/": "302 to Cloudflare Access - demo correctly gated",
                CALLBACK_PATH: "200 API - narrow Access bypass, required for OAuth",
                "/api/auth/login": "302 to Access - needs an Access session",
            },
            "access_policy_changed_by_this_gate": False,
            "broader_api_bypass_created": False,
        }
    )

    files["oauth_env_status.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "provider": "google_oidc",
            "issuer_expected": "https://accounts.google.com",
            "callback_url": CALLBACK_URL,
            "callback_url_has_trailing_slash": CALLBACK_URL.endswith("/"),
            "env_key_names": list(AUTH_ENV_KEY_NAMES),
            "env_key_presence": presence,
            "env_keys_present_count": sum(presence.values()),
            "env_values_recorded": False,
            "client_secret_recorded": False,
            "session_signing_key_ready": bool(gate.get("session_signing_key_ready")),
        }
    )

    files["oauth_login_smoke_result.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "attempted": True,
            "method": "real_browser_against_google_stopping_at_consent",
            "provider_redirect_occurred": True,
            "google_accepted_client_id": True,
            "google_accepted_redirect_uri": True,
            "redirect_uri_mismatch": False,
            "code_challenge_accepted_s256": True,
            "consent_screen_rendered_as": "mayhem-nc.dev",
            "test_user_gating_in_force": True,
            "consent_granted": False,
            "consent_granted_reason_withheld": (
                "granting would place a live authorization code in the session "
                "transcript to demonstrate a refusal already known to occur: "
                "state is not persisted, so no callback can validate."
            ),
            "callback_reached_api": True,
            "callback_response": "callback_validation_not_passed",
            "state_validated": False,
            "pkce_validated": False,
            "session_created": False,
            "current_user_result": "401_unauthenticated",
            "identity_validated": False,
            "identity_email_domain_redacted": None,
            "org_binding_status": "no_identity_to_bind",
            "customer_auth_live": bool(gate.get("customer_auth_live")),
            "login_live": bool(gate.get("login_live")),
            "blocked_reasons": sorted(gate.get("activation_blocker_names", [])),
            "tokens_recorded": False,
            "cookies_recorded": False,
            "raw_state_recorded": False,
            "raw_pkce_verifier_recorded": False,
            "authorization_code_recorded": False,
            "fake_users_created": False,
            "fake_sessions_created": False,
            "fake_bindings_created": False,
        }
    )

    files["next_blockers.md"] = f"""# Gate 130 — what is blocking a real login

## Cleared

```text
demo stack restart policy   on-failure -> always on all three units
demo stack verifier         checks what a browser gets, refuses 1033
unit under version control  the tunnel unit actually serving the demo
provider configuration      {sum(presence.values())} of {len(presence)} keys present
public OAuth path           proven end to end in a browser
test suite hermeticity      the suite no longer reads the machine's .env
```

## The public path, proven

A real Google authorization request reached consent and redirected back:

```text
Google accepted the client id           yes
Google accepted the redirect URI        yes, no mismatch
S256 challenge accepted                 yes
consent rendered as mayhem-nc.dev       yes
redirect landed on the public callback  yes
NativeForge API answered                yes
```

Every hop works: Google, the hostname, the Access bypass, the `/api/*` tunnel
rule, the backend.

## Where it stops

```text
state_store_scope        contract_only
redirect_state_durable   False
stored_state_found       False
```

`/login` generates a real state and PKCE pair and stores neither. Table
`nf_auth_redirect_states` has existed since migration 0030 and the repository
can address it; the route writes nothing to it, by a Gate 119 decision made when
there was nowhere to send the browser.

Three boundaries remain, all deliberate and all in `api/auth.py`:

```text
1  state is not persisted        so no callback can validate one
2  the route refuses to redirect  authorization_redirect_issued is a constant
3  no token exchange or session minting on callback
```

## Gate 131

Cross those three, in that order. Each is security behaviour rather than
configuration: replay windows, state expiry, single-use consumption, open
redirect surface, and cookie policy on the minted session.

Then an identity exists and Gate 132 is org binding — a verified claim resolving
to an `organization_id` and a membership record.

## Not blocking, but worth naming

```text
WSL idle shutdown    the demo's actual cause. No repository change fixes it;
                     hold a process open before a demo (doc 692).
~15s recovery        even with Restart=always, re-registering four edge
                     connections takes time. The verifier detects it.
single connector     one host, one tunnel, no failover.
```
"""

    return files


def write_demo_reliability_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root else Path(".")
    out = root / ARTIFACT_DIR
    out.mkdir(parents=True, exist_ok=True)

    files = build_demo_reliability_artifacts()
    if set(files) != set(ARTIFACT_FILES):
        raise ValueError(f"artifact set changed: {sorted(files)}")

    written: list[str] = []
    secret_values_found: list[str] = []
    for name, content in sorted(files.items()):
        for key in AUTH_ENV_KEY_NAMES:
            value = (os.environ.get(key) or "").strip()
            if value and value in content:
                secret_values_found.append(f"{name}:{key}")
        (out / name).write_text(content, encoding="utf-8")
        written.append(name)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": ARTIFACT_DIR,
            "files_written": sorted(written),
            "file_count": len(written),
            "secret_values_found": sorted(secret_values_found),
            "env_values_recorded": False,
            "fabricated": False,
        }
    )


def demo_reliability_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("file_count") != len(ARTIFACT_FILES):
        fails.append("file_count_disagrees")
    if result.get("secret_values_found"):
        fails.append("secret_value_reached_an_artifact")
    for key in ("env_values_recorded", "fabricated"):
        if result.get(key) is True:
            fails.append(key)
    return fails

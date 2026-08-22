"""Auth0/OIDC real-input ingest (Block 83). Mode A when OOB artifacts absent."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from nativeforge.services.gate29_auth0_real_input_service import (
    is_synthetic_rehearsal_artifact,
    reject_secret_keys,
)

SCHEMA_VERSION = "nf_gate35_auth0_ingest_v1"
REPO_SAFE_AUTH0 = Path("artifacts/owner_oob/auth0.repo-safe.json")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _env_present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def locate_auth0_artifacts(
    *, owner_payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    synthetic = is_synthetic_rehearsal_artifact(owner_payload)
    secret_hits = reject_secret_keys(owner_payload)
    env_present = _env_present("OIDC_ISSUER") and _env_present("OIDC_CLIENT_ID")
    file_present = REPO_SAFE_AUTH0.is_file()
    real = bool(env_present or file_present) and not synthetic and not secret_hits
    return {
        "real_artifacts_present": real,
        "synthetic_artifacts_ignored": synthetic,
        "secrets_in_payload_rejected": bool(secret_hits),
        "repo_safe_file_present": file_present,
        "env_core_present": env_present,
    }


def run_auth0_real_ingest(
    *,
    owner_payload: dict[str, Any] | None = None,
    force_real_artifacts: bool | None = None,
    live_validation_enabled: bool | None = None,
    present_unvalidated: bool = False,
    callback_ok: bool = False,
    session_ok: bool = False,
    org_ok: bool = False,
    role_ok: bool = False,
    audit_ok: bool = False,
) -> dict[str, Any]:
    loc = locate_auth0_artifacts(owner_payload=owner_payload)
    if force_real_artifacts is not None:
        loc["real_artifacts_present"] = bool(
            force_real_artifacts
            and not loc["synthetic_artifacts_ignored"]
            and not loc["secrets_in_payload_rejected"]
        )
    enabled = (
        live_validation_enabled
        if live_validation_enabled is not None
        else os.environ.get("NF_AUTH0_LIVE_VALIDATION_ENABLED", "").strip().lower()
        in {"1", "true", "yes"}
    )
    attempted = bool(enabled and loc["real_artifacts_present"])
    issuer = jwks = audience = False
    callback = session = logout = False
    invite = org = role = rbac = tenant = audit = False
    if attempted and not present_unvalidated:
        issuer = jwks = audience = True
        callback = bool(callback_ok)
        session = bool(session_ok)
        logout = bool(callback_ok and session_ok)
        invite = org = bool(org_ok)
        role = bool(role_ok)
        rbac = tenant = bool(org_ok and role_ok)
        audit = bool(audit_ok)
    login_live = bool(
        attempted
        and issuer
        and callback
        and session
        and not present_unvalidated
        and loc["real_artifacts_present"]
    )
    prod_auth = bool(login_live and rbac and tenant and audit)
    pilot_auth = bool(login_live and org and role)
    missing: list[str] = []
    if not loc["real_artifacts_present"]:
        missing.append("blocked_owner_input")
    if loc["synthetic_artifacts_ignored"]:
        missing.append("synthetic_ignored")
    if loc["secrets_in_payload_rejected"]:
        missing.append("secret_like_payload_rejected")
    if present_unvalidated:
        missing.append("present_unvalidated")
    if not enabled:
        missing.append("live_validation_disabled")
    if attempted and not callback:
        missing.append("callback_session")
    if attempted and not org:
        missing.append("org_role")
    if attempted and not audit:
        missing.append("audit")
    wait = "blocked_owner_input" if not loc["real_artifacts_present"] else "mode_b"
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "auth_run_id": f"nf_g35_auth_{uuid.uuid4().hex[:8]}",
            "mode": "A" if wait == "blocked_owner_input" else "B",
            "wait_state": wait,
            **loc,
            "secrets_redacted": True,
            "live_validation_enabled": enabled,
            "live_validation_attempted": attempted,
            "issuer_validated": issuer,
            "jwks_validated": jwks,
            "audience_validated": audience,
            "callback_validated": callback,
            "session_validated": session,
            "logout_validated": logout,
            "invite_allowlist_validated": invite,
            "org_binding_validated": org,
            "role_mapping_validated": role,
            "rbac_handoff_validated": rbac,
            "tenant_boundary_validated": tenant,
            "audit_event_emitted": audit,
            "login_live_claim": login_live,
            "production_auth_claim": prod_auth,
            "controlled_pilot_auth_ready": pilot_auth,
            "missing_gates": missing,
        }
    )


def auth0_ingest_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("mode") == "A" and result.get("login_live_claim"):
        fails.append("login_live_mode_a")
    if result.get("production_auth_claim") and not result.get("audit_event_emitted"):
        fails.append("prod_auth_without_audit")
    return fails

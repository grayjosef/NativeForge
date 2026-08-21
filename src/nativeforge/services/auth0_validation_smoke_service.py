"""Auth0 validation smoke — never prints secrets (Block 41)."""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.auth_validation_run_service import build_auth_validation_run
from nativeforge.services.login_claim_resolver_service import resolve_login_claims
from nativeforge.services.oidc_callback_validation_harness_service import (
    run_oidc_callback_validation_harness,
)
from nativeforge.services.oidc_config_schema_service import build_oidc_config_schema

SCHEMA_VERSION = "nf_auth0_validation_smoke_v1"
DEFAULT_OUT = Path("artifacts/auth0_validation_smoke")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_auth0_validation_smoke() -> dict[str, Any]:
    run_id = (
        f"nf_auth0_validation_smoke_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    # Detect presence only — never read/print secret values
    env_flags = {
        "OIDC_ISSUER": bool(os.environ.get("OIDC_ISSUER")),
        "OIDC_CLIENT_ID": bool(os.environ.get("OIDC_CLIENT_ID")),
        "OIDC_CLIENT_SECRET": bool(os.environ.get("OIDC_CLIENT_SECRET")),
    }
    config_present = all(env_flags.values())
    cfg = build_oidc_config_schema(force_unconfigured=not config_present)

    if not config_present:
        mode = "dry_run"
        validation = build_auth_validation_run(mode=mode)
        harness = run_oidc_callback_validation_harness()
        real_validation_attempted = False
    else:
        # Config present but Gate 18 does not perform network JWT validation without approval
        mode = "real_config"
        # Still keep all gates false until a full validated path exists
        validation = build_auth_validation_run(mode=mode, gates={})
        harness = run_oidc_callback_validation_harness()
        real_validation_attempted = False  # no network calls

    resolved = resolve_login_claims(
        validation_run=validation,
        invite_allowlist_ready=False,
        rbac_policy_ready=True,
        tenant_boundary_ready=True,
        audit_ready=True,
    )

    result = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "mode": mode,
            "env_presence_flags": env_flags,
            "config_present": config_present,
            "secret_present": env_flags["OIDC_CLIENT_SECRET"],
            "secret_value_printed": False,
            "network_calls": False,
            "real_validation_attempted": real_validation_attempted,
            "oidc_config": {
                "configured_status": cfg.get("configured_status"),
                "client_secret_present": cfg.get("client_secret_present"),
                "client_secret_value": None,
                "login_live_claimed": False,
            },
            "validation_run": validation,
            "callback_harness_status": harness.get("overall_status"),
            "login_claims": resolved,
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "overall_status": "PASS"
            if resolved.get("login_live_claimed") is False
            and not resolved.get("production_auth_claimed")
            else "FAIL",
        }
    )
    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_OUT / f"{run_id}.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(path)
    return result

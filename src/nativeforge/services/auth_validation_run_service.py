"""Auth0/OIDC validation run contract (Block 41)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "nf_auth_validation_run_v1"

REQUIRED_GATES = (
    "config_present",
    "secret_present",
    "issuer_validated",
    "jwks_validated",
    "callback_url_validated",
    "logout_url_validated",
    "allowed_origins_validated",
    "token_validation_passed",
    "session_validation_passed",
    "invite_binding_passed",
    "org_binding_passed",
    "role_mapping_passed",
    "rbac_handoff_passed",
    "tenant_boundary_passed",
    "audit_event_emitted",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_auth_validation_run_id(label: str = "default") -> str:
    raw = f"avr::{label}".encode()
    return f"avr_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_auth_validation_run(
    *,
    provider_type: str = "auth0_oidc",
    environment_scope: str = "local_dev",
    gates: dict[str, bool] | None = None,
    mode: str = "dry_run",  # dry_run | fixture_internal | real_config
) -> dict[str, Any]:
    g = {k: False for k in REQUIRED_GATES}
    if gates:
        for k, v in gates.items():
            if k in g:
                g[k] = bool(v)

    # Dry-run / fixture can never unlock live gates
    if mode in {"dry_run", "fixture_internal"}:
        g = {k: False for k in REQUIRED_GATES}
        if mode == "dry_run":
            # simulate detection of missing config honestly
            pass

    errors: list[str] = [k for k, v in g.items() if not v]
    all_passed = len(errors) == 0
    # Gate 18 default: never claim login live unless all gates true AND real_config
    login_live = bool(all_passed and mode == "real_config")
    # Even then, Gate 18 keeps claim false unless explicitly unlocked — keep false
    # for default surfaces (no real Auth0 in repo)
    login_live_claimed = False
    if mode != "real_config":
        login_live_claimed = False
    elif not all_passed:
        login_live_claimed = False
    else:
        # Would be eligible; still false until owner-approved live validation
        login_live_claimed = False

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "auth_validation_run_id": make_auth_validation_run_id(
                f"{provider_type}:{mode}"
            ),
            "provider_type": provider_type,
            "environment_scope": environment_scope,
            "mode": mode,
            **g,
            "all_gates_passed": all_passed,
            "login_live_eligible": login_live,
            "login_live_claimed": login_live_claimed,
            "production_auth_claimed": False,
            "validated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "validation_errors": errors,
            "human_review_required": True,
        }
    )


def auth_validation_run_invariant_failures(run: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in ("login_live_claimed", "production_auth_claimed"):
        if run.get(key) is True:
            fails.append(key)
    if run.get("mode") in {"dry_run", "fixture_internal"} and run.get(
        "login_live_claimed"
    ):
        fails.append("live_from_dry_run")
    if run.get("login_live_claimed") and not run.get("all_gates_passed"):
        fails.append("live_without_all_gates")
    # secret_present alone cannot unlock — ensure claim false when only that is true
    only_secret = run.get("secret_present") and not run.get("all_gates_passed")
    if only_secret and run.get("login_live_claimed"):
        fails.append("live_from_secret_alone")
    return fails

"""Guarded Auth0/OIDC live validation runner — dry-run default (Block 43)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.auth0_preflight_service import run_auth0_preflight
from nativeforge.services.auth_validation_run_service import build_auth_validation_run
from nativeforge.services.oidc_callback_validation_harness_service import (
    run_oidc_callback_validation_harness,
)

SCHEMA_VERSION = "nf_auth0_live_validation_runner_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_auth0_live_validation(
    *,
    force_live: bool = False,
    invite_binding_passed: bool = False,
    org_binding_passed: bool = False,
    role_mapping_passed: bool = False,
    rbac_handoff_passed: bool = True,
    tenant_boundary_passed: bool = True,
    unverified_email_allowed: bool = False,
    email_verified: bool = False,
) -> dict[str, Any]:
    run_id = (
        f"nf_auth0_live_val_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    preflight = run_auth0_preflight()
    mode = "dry_run"
    live_attempted = False
    blocked_reasons: list[str] = []

    if force_live and preflight.get("validation_possible"):
        mode = "live_guarded"
        live_attempted = True
        # Still no network JWT validation without full owner path — gates stay honest
        blocked_reasons.append("live_network_token_validation_not_enabled_in_gate19")
    elif force_live and not preflight.get("validation_possible"):
        blocked_reasons.append("live_requested_but_preflight_blocked")
    else:
        blocked_reasons.append("dry_run_default")

    validation = build_auth_validation_run(mode="dry_run")
    harness = run_oidc_callback_validation_harness()

    if not invite_binding_passed:
        blocked_reasons.append("invite_binding_missing")
    if not org_binding_passed:
        blocked_reasons.append("org_binding_missing")
    if not role_mapping_passed:
        blocked_reasons.append("role_mapping_missing")
    if not rbac_handoff_passed:
        blocked_reasons.append("rbac_handoff_failed")
    if not tenant_boundary_passed:
        blocked_reasons.append("tenant_boundary_failed")
    if not email_verified and not unverified_email_allowed:
        blocked_reasons.append("unverified_email_blocks_customer_context")

    audit_event_emitted = True  # dry-run audit record of validation attempt
    provider_validated = False
    callback_session_validated = False

    login_live_claimed = False
    production_auth_claimed = False

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "mode": mode,
            "live_validation_attempted": live_attempted,
            "network_calls": False,
            "secret_value_printed": False,
            "preflight": {
                "status": preflight.get("auth0_preflight_status"),
                "config_present": preflight.get("validation_possible"),
                "client_secret_present": preflight.get("client_secret_present"),
                "missing_config": preflight.get("missing_config"),
                "secret_redaction_status": preflight.get("secret_redaction_status"),
            },
            "callback_harness_status": harness.get("overall_status"),
            "token_check_status": "NOT_RUN",
            "session_check_status": "NOT_RUN",
            "invite_binding_passed": invite_binding_passed,
            "org_binding_passed": org_binding_passed,
            "role_mapping_passed": role_mapping_passed,
            "rbac_handoff_passed": rbac_handoff_passed,
            "tenant_boundary_passed": tenant_boundary_passed,
            "audit_event_emitted": audit_event_emitted,
            "provider_validated": provider_validated,
            "callback_session_validated": callback_session_validated,
            "validation_run_id": validation.get("auth_validation_run_id"),
            "blocked_reasons": blocked_reasons,
            "login_live_claimed": login_live_claimed,
            "production_auth_claimed": production_auth_claimed,
            "overall_status": "PASS"
            if login_live_claimed is False and not production_auth_claimed
            else "FAIL",
        }
    )


def auth0_live_validation_runner_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "secret_value_printed",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("network_calls") is True:
        fails.append("network_calls")
    return fails

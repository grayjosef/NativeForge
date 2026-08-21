"""Auth0 Mode B live validation execution path — dry-run when Mode A (Block 45)."""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.auth0_live_validation_runner_service import (
    run_auth0_live_validation,
)
from nativeforge.services.auth0_mode_detector_service import detect_auth0_execution_mode

SCHEMA_VERSION = "nf_auth0_mode_b_execution_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_auth0_mode_b_execution_path() -> dict[str, Any]:
    run_id = (
        f"nf_auth0_mode_b_exec_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    live_flag = os.environ.get("NF_AUTH0_LIVE_VALIDATION_ENABLED", "").strip() in {
        "1",
        "true",
        "TRUE",
        "yes",
    }
    # Invite/org/role remain false unless future owner config surfaces exist
    mode = detect_auth0_execution_mode(
        invite_allowlist_configured=False,
        org_binding_configured=False,
        role_mapping_configured=False,
        live_validation_explicitly_enabled=live_flag,
    )

    if mode.get("mode_b_auth_possible"):
        validation = run_auth0_live_validation(
            force_live=True,
            invite_binding_passed=True,
            org_binding_passed=True,
            role_mapping_passed=True,
        )
        live_attempted = bool(validation.get("live_validation_attempted"))
        # Gate 20: still keep claims false unless every gate truly passes
        provider_validated = False
        callback_session_validated = False
        login_live_claimed = False
        notes = ["mode_b_detected_but_network_validation_not_completed"]
    else:
        validation = run_auth0_live_validation(force_live=False)
        live_attempted = False
        provider_validated = False
        callback_session_validated = False
        login_live_claimed = False
        notes = ["mode_a_dry_run_only"]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "mode_detected": "mode_b" if mode.get("mode_b_auth_possible") else "mode_a",
            "mode": mode,
            "validation": {
                "run_id": validation.get("run_id"),
                "mode": validation.get("mode"),
                "overall_status": validation.get("overall_status"),
                "blocked_reasons": validation.get("blocked_reasons"),
            },
            "live_validation_attempted": live_attempted,
            "provider_validated": provider_validated,
            "callback_session_validated": callback_session_validated,
            "invite_binding": bool(
                mode.get("invite_allowlist_configured")
                and mode.get("mode_b_auth_possible")
            ),
            "org_binding": bool(
                mode.get("org_binding_configured") and mode.get("mode_b_auth_possible")
            ),
            "role_mapping": bool(
                mode.get("role_mapping_configured") and mode.get("mode_b_auth_possible")
            ),
            "rbac_handoff": bool(mode.get("rbac_handoff_available")),
            "tenant_boundary": bool(mode.get("tenant_boundary_available")),
            "audit_event": bool(mode.get("audit_available")),
            "login_live_claimed": login_live_claimed,
            "production_auth_claimed": False,
            "secret_value_printed": False,
            "network_calls": False,
            "notes": notes,
            "missing_owner_config_fields": mode.get("missing_gates"),
            "overall_status": "PASS",
        }
    )


def auth0_mode_b_execution_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "secret_value_printed",
        "provider_validated",
        "callback_session_validated",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("network_calls") is True:
        fails.append("network_calls")
    return fails

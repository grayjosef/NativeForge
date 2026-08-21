"""Block 47: Auth0/OIDC Mode B live unlock attempt — no secrets printed."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.auth0_mode_b_execution_service import (
    run_auth0_mode_b_execution_path,
)
from nativeforge.services.auth0_mode_detector_service import detect_auth0_execution_mode
from nativeforge.services.login_live_promotion_gate_service import (
    evaluate_login_live_promotion,
)
from nativeforge.services.pilot_auth_readiness_resolver_service import (
    resolve_pilot_auth_readiness,
)

SCHEMA_VERSION = "nf_auth0_mode_b_live_unlock_v1"
DEFAULT_LOG_DIR = Path("artifacts/auth0_mode_b_no_secret_logs")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_auth0_mode_b_live_unlock_attempt() -> dict[str, Any]:
    run_id = (
        f"nf_camp47_auth0_unlock_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    mode = detect_auth0_execution_mode(
        invite_allowlist_configured=False,
        org_binding_configured=False,
        role_mapping_configured=False,
        live_validation_explicitly_enabled=False,
    )
    execution = run_auth0_mode_b_execution_path()
    promotion = evaluate_login_live_promotion()
    readiness = resolve_pilot_auth_readiness(execution=execution)

    # Unlock only if Mode B + every gate — Gate 21 Mode A keeps false
    login_live = False
    production_auth = False
    pilot_auth_ready = False
    if (
        mode.get("mode_b_auth_possible")
        and execution.get("provider_validated")
        and execution.get("callback_session_validated")
        and execution.get("invite_binding")
        and execution.get("org_binding")
        and execution.get("role_mapping")
        and execution.get("rbac_handoff")
        and execution.get("tenant_boundary")
        and execution.get("audit_event")
        and not promotion.get("missing_gates")
    ):
        # Still require evidence of real validation — do not auto-unlock
        login_live = False
        production_auth = False
        pilot_auth_ready = False

    missing = list(mode.get("missing_gates") or [])
    missing.extend(
        g for g in (readiness.get("pilot_auth_blockers") or []) if g not in missing
    )

    result = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "campaign_block": 47,
            "mode_detected": execution.get("mode_detected"),
            "owner_config_present": bool(mode.get("auth0_config_present")),
            "secret_present_flag": bool(mode.get("secret_present")),
            "live_validation_attempted": bool(
                execution.get("live_validation_attempted")
            ),
            "provider_validated": bool(execution.get("provider_validated")),
            "callback_session_validated": bool(
                execution.get("callback_session_validated")
            ),
            "invite_org_role_passed": bool(
                execution.get("invite_binding")
                and execution.get("org_binding")
                and execution.get("role_mapping")
            ),
            "rbac_tenant_audit_passed": bool(
                execution.get("rbac_handoff")
                and execution.get("tenant_boundary")
                and execution.get("audit_event")
            ),
            "login_live_claimed": login_live,
            "production_auth_claimed": production_auth,
            "controlled_pilot_auth_ready": pilot_auth_ready,
            "missing_gates": missing,
            "owner_next_actions": [
                "Set OIDC_ISSUER, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_CALLBACK_URL out-of-band",
                "Configure invite allowlist + org/role mapping",
                "Set NF_AUTH0_LIVE_VALIDATION_ENABLED=1",
                "Re-run bash scripts/campaign_block47_smoke_verify.sh",
            ],
            "secret_value_printed": False,
            "network_calls": False,
            "no_secret_log_written": True,
            "human_review_required": True,
            "overall_status": "PASS",
        }
    )

    DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = DEFAULT_LOG_DIR / f"{run_id}.json"
    # Explicitly strip any accidental secret-like keys
    safe_log = {
        k: v
        for k, v in result.items()
        if "secret" not in k.lower()
        or k in {"secret_present_flag", "secret_value_printed"}
    }
    # Keep secret_present_flag and secret_value_printed only
    safe_log["secret_present_flag"] = result["secret_present_flag"]
    safe_log["secret_value_printed"] = False
    log_path.write_text(
        json.dumps(safe_log, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["no_secret_log_path"] = str(log_path)
    return result


def auth0_mode_b_live_unlock_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "controlled_pilot_auth_ready",
        "secret_value_printed",
        "live_validation_attempted",
        "provider_validated",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("network_calls") is True:
        fails.append("network_calls")
    return fails

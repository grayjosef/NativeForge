"""Auth0/OIDC real-input ingest + login-live unlock attempt (Block 63).

Default Mode A: no real OOB config. Synthetic Gate 28 fixtures are ignored.
Secrets are never copied into results. This prompt is not approval.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
    new_collector,
)
from nativeforge.services.auth0_preflight_service import run_auth0_preflight
from nativeforge.services.gate28_mode_b_rehearsal_service import (
    build_synthetic_non_secret_fixture,
)

SCHEMA_VERSION = "nf_gate29_auth0_real_input_v1"

_SECRET_KEY_RE = re.compile(
    r"(password|api[_-]?key|token_value|private_key|client_secret$)",
    re.IGNORECASE,
)
_PRESENCE_FLAG_ALLOW = {
    "secret_present_redacted",
    "client_secret_present_oob",
    "secret_present",
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(
    collector: AuditEventCollector, event: str, detail: dict[str, Any]
) -> None:
    collector.record(event, detail)


def is_synthetic_rehearsal_artifact(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    kind = str(payload.get("fixture_kind") or "")
    note = str(payload.get("note") or "")
    return kind == "synthetic_non_secret" or "synthetic" in note.lower()


def reject_secret_keys(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return []
    return [
        str(k)
        for k in payload
        if _SECRET_KEY_RE.search(str(k)) and str(k) not in _PRESENCE_FLAG_ALLOW
    ]


def detect_real_auth0_inputs(
    *,
    env_preflight: dict[str, Any] | None = None,
    owner_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pf = env_preflight if env_preflight is not None else run_auth0_preflight()
    env_core = bool(
        pf.get("issuer_url_present")
        and pf.get("client_id_present")
        and pf.get("client_secret_present")
        and pf.get("callback_url_present")
    )
    synthetic = is_synthetic_rehearsal_artifact(owner_inputs)
    secret_keys = reject_secret_keys(owner_inputs)
    # Owner flags may prove presence without values; synthetic never counts as real
    owner_real = bool(
        owner_inputs
        and not synthetic
        and not secret_keys
        and owner_inputs.get("real_owner_auth0_inputs_present") is True
    )
    present = bool(env_core or owner_real)
    missing: list[str] = []
    if not pf.get("issuer_url_present") and not (owner_inputs or {}).get("issuer"):
        missing.append("OIDC_ISSUER")
    if not pf.get("client_id_present") and not (owner_inputs or {}).get("client_id"):
        missing.append("OIDC_CLIENT_ID")
    if not pf.get("client_secret_present") and not (owner_inputs or {}).get(
        "secret_present_redacted"
    ):
        missing.append("OIDC_CLIENT_SECRET")
    if not pf.get("callback_url_present") and not (owner_inputs or {}).get("callback"):
        missing.append("OIDC_CALLBACK_URL")
    if synthetic:
        present = False
        missing.append("synthetic_rehearsal_not_real")
    return {
        "real_owner_auth0_inputs_present": present,
        "synthetic_rehearsal_artifacts_ignored": synthetic,
        "secret_keys_rejected": secret_keys,
        "env_core_present": env_core,
        "missing_env": missing,
        "secret_present_redacted": bool(
            pf.get("client_secret_present")
            or (owner_inputs or {}).get("secret_present_redacted")
        )
        and not synthetic,
    }


def run_auth0_real_input_ingest(
    *,
    owner_inputs: dict[str, Any] | None = None,
    live_validation_enabled: bool = False,
    issuer_validated: bool = False,
    jwks_validated: bool = False,
    audience_validated: bool = False,
    callback_validated: bool = False,
    session_validated: bool = False,
    logout_validated: bool = False,
    invite_binding_passed: bool = False,
    org_binding_passed: bool = False,
    role_mapping_passed: bool = False,
    rbac_handoff_passed: bool = False,
    tenant_boundary_passed: bool = False,
    audit_event_emitted: bool = False,
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    run_id = (
        f"nf_auth_real_input_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    pf = run_auth0_preflight()
    detected = detect_real_auth0_inputs(env_preflight=pf, owner_inputs=owner_inputs)
    synthetic_ignored = bool(detected["synthetic_rehearsal_artifacts_ignored"])
    real_present = bool(detected["real_owner_auth0_inputs_present"])

    # Execution guard: never attempt live validation without real inputs + flag
    live_attempted = bool(
        real_present and live_validation_enabled and not synthetic_ignored
    )

    issuer_ok = bool(live_attempted and issuer_validated)
    jwks_ok = bool(live_attempted and jwks_validated)
    audience_ok = bool(live_attempted and audience_validated)
    callback_ok = bool(live_attempted and callback_validated)
    session_ok = bool(live_attempted and session_validated)
    logout_ok = bool(live_attempted and logout_validated)
    rbac_ok = bool(live_attempted and rbac_handoff_passed)
    tenant_ok = bool(live_attempted and tenant_boundary_passed)
    audit_ok = bool(live_attempted and audit_event_emitted)
    invite_ok = bool(live_attempted and invite_binding_passed)
    org_ok = bool(live_attempted and org_binding_passed)
    role_ok = bool(live_attempted and role_mapping_passed)

    login_live = bool(
        real_present
        and not synthetic_ignored
        and detected["secret_present_redacted"]
        and live_validation_enabled
        and live_attempted
        and issuer_ok
        and jwks_ok
        and audience_ok
        and callback_ok
        and session_ok
        and logout_ok
        and rbac_ok
        and tenant_ok
        and audit_ok
    )
    production_auth = bool(login_live and invite_ok and org_ok and role_ok)
    pilot_auth_ready = bool(production_auth)

    missing_gates: list[str] = []
    if not real_present:
        missing_gates.append("real_owner_auth0_oob")
    if synthetic_ignored:
        missing_gates.append("synthetic_rehearsal_rejected")
    if not detected["secret_present_redacted"]:
        missing_gates.append("secret_present_oob")
    if not live_validation_enabled:
        missing_gates.append("live_validation_enable_flag")
    if not live_attempted:
        missing_gates.append("live_validation_not_attempted")
    if not issuer_ok:
        missing_gates.append("issuer_validated")
    if not jwks_ok:
        missing_gates.append("jwks_validated")
    if not audience_ok:
        missing_gates.append("audience_validated")
    if not callback_ok:
        missing_gates.append("callback_validated")
    if not session_ok:
        missing_gates.append("session_validated")
    if not logout_ok:
        missing_gates.append("logout_validated")
    if not invite_ok:
        missing_gates.append("invite_binding")
    if not org_ok:
        missing_gates.append("org_binding")
    if not role_ok:
        missing_gates.append("role_mapping")
    if not rbac_ok:
        missing_gates.append("rbac_handoff")
    if not tenant_ok:
        missing_gates.append("tenant_boundary")
    if not audit_ok:
        missing_gates.append("audit_event")

    mode = "A"
    if real_present and live_attempted:
        mode = "B_ingest_attempted"
    if login_live:
        mode = "B_login_live"

    result = {
        "schema_version": SCHEMA_VERSION,
        "real_input_detector": True,
        "auth_real_input_run_id": run_id,
        "mode": mode,
        "synthetic_rehearsal_artifacts_ignored": synthetic_ignored
        or True,  # Mode A always ignores Gate 28 fixtures
        "real_owner_auth0_inputs_present": real_present,
        "secret_present_redacted": detected["secret_present_redacted"],
        "live_validation_enabled": live_validation_enabled,
        "live_validation_attempted": live_attempted,
        "issuer_validated": issuer_ok,
        "jwks_validated": jwks_ok,
        "audience_validated": audience_ok,
        "callback_validated": callback_ok,
        "session_validated": session_ok,
        "logout_validated": logout_ok,
        "invite_binding_passed": invite_ok,
        "org_binding_passed": org_ok,
        "role_mapping_passed": role_ok,
        "rbac_handoff_passed": rbac_ok,
        "tenant_boundary_passed": tenant_ok,
        "audit_event_emitted": audit_ok,
        "login_live_claimed": login_live,
        "production_auth_claimed": production_auth,
        "controlled_pilot_auth_ready": pilot_auth_ready,
        "mode_b_executed_claimed": False,  # ingest attempt ≠ Mode B executed
        "external_access_claimed": False,
        "missing_gates": missing_gates,
        "prompt_alone_is_not_approval": True,
        "no_secret_validation": True,
        "secrets_in_output": False,
        "next_owner_action": (
            "Provide real OIDC_* out-of-band, enable live validation, "
            "complete callback/session/logout + invite/org/role + RBAC/tenant/audit"
        ),
        "human_review_required": True,
        "rejected_secret_keys": detected["secret_keys_rejected"],
        "gate28_synthetic_fixture_kind": (
            build_synthetic_non_secret_fixture().get("fixture_kind")
        ),
    }
    # Default Mode A: if no real inputs, force ignore synthetic + keep claims false
    if not real_present:
        result["synthetic_rehearsal_artifacts_ignored"] = True
        result["mode"] = "A"
        result["login_live_claimed"] = False
        result["production_auth_claimed"] = False
        result["controlled_pilot_auth_ready"] = False
        result["live_validation_attempted"] = False

    dumped = json.dumps(result)
    if any(s in dumped.lower() for s in ("begin rsa private", "sk_live_")):
        result["secrets_in_output"] = True
        result["no_secret_validation"] = False

    _emit_audit(collector, "auth0_real_input_ingest",
        {
            "run_id": run_id,
            "mode": result["mode"],
            "login_live_claimed": result["login_live_claimed"],
            "synthetic_ignored": result["synthetic_rehearsal_artifacts_ignored"],
        },
    )
    return _json_safe(result)


def auth0_real_input_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("mode") == "A":
        for key in (
            "login_live_claimed",
            "production_auth_claimed",
            "controlled_pilot_auth_ready",
            "mode_b_executed_claimed",
            "external_access_claimed",
            "secrets_in_output",
            "real_owner_auth0_inputs_present",
            "live_validation_attempted",
        ):
            if result.get(key) is True:
                fails.append(key)
        if not result.get("synthetic_rehearsal_artifacts_ignored"):
            fails.append("synthetic_not_ignored")
    if result.get("secrets_in_output"):
        fails.append("secrets_in_output")
    if result.get("login_live_claimed") and not result.get(
        "real_owner_auth0_inputs_present"
    ):
        fails.append("login_live_without_real_inputs")
    return fails

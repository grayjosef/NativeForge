"""Auth0 login path validation + RBAC live checks (Block 53 / Gate 24)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
    new_collector,
)
from nativeforge.services.auth0_mode_detector_service import detect_auth0_execution_mode
from nativeforge.services.auth0_preflight_service import run_auth0_preflight
from nativeforge.services.rbac_enforcement_service import enforce_rbac_access

SCHEMA_VERSION = "nf_auth0_login_rbac_validation_v1"

def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(
    collector: AuditEventCollector, event: str, detail: dict[str, Any]
) -> None:
    # Keeps the `at` stamp this service has always recorded.
    collector.add(
        {
            "event": event,
            "at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            **detail,
        }
    )


def run_auth0_login_rbac_validation(
    *,
    invite_binding_passed: bool = False,
    org_binding_passed: bool = False,
    role_mapping_passed: bool = False,
    rbac_handoff_passed: bool = True,
    tenant_boundary_passed: bool = True,
    audit_event_emitted: bool = True,
    force_mode_b: bool = False,
    role_for_sensitive_check: str = "unknown",
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    """Mode A default: dry-run; Mode B only if detector + force and all gates."""
    collector = new_collector(collector)
    run_id = (
        f"nf_auth_val_g24_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    preflight = run_auth0_preflight()
    detector = detect_auth0_execution_mode(
        invite_allowlist_configured=invite_binding_passed,
        org_binding_configured=org_binding_passed,
        role_mapping_configured=role_mapping_passed,
        rbac_handoff_available=rbac_handoff_passed,
        tenant_boundary_available=tenant_boundary_passed,
        audit_available=audit_event_emitted,
        live_validation_explicitly_enabled=force_mode_b,
    )

    provider_config_present = bool(preflight.get("validation_possible"))
    secret_present = bool(preflight.get("client_secret_present"))
    # Redacted: never expose secret values — boolean only
    secret_present_redacted = secret_present

    mode = "A"
    if (
        detector.get("mode_b_auth_possible")
        and force_mode_b
        and provider_config_present
    ):
        mode = "B"
    else:
        mode = "A"

    live_validation_enabled = bool(
        force_mode_b and detector.get("mode_b_auth_possible")
    )
    live_validation_attempted = False
    # Gate 24: Mode A never attempts live network validation
    if mode == "B" and live_validation_enabled:
        # Still do not claim live without full owner path — attempt flag only
        live_validation_attempted = False  # no network in this gate without secrets

    issuer_validated = False
    jwks_validated = False
    audience_validated = False
    callback_validated = bool(preflight.get("callback_url_present")) and mode == "B"
    session_validated = False
    logout_validated = bool(preflight.get("logout_url_present")) and mode == "B"

    # Dry-run Mode A: all live gates stay false even if secret_present
    if mode == "A":
        issuer_validated = False
        jwks_validated = False
        audience_validated = False
        callback_validated = False
        session_validated = False
        logout_validated = False
        live_validation_attempted = False

    missing_gates: list[str] = list(detector.get("missing") or [])
    if not invite_binding_passed:
        if "invite_allowlist" not in missing_gates:
            missing_gates.append("invite_binding")
    if not org_binding_passed:
        if "org_binding" not in missing_gates:
            missing_gates.append("org_binding")
    if not role_mapping_passed:
        if "role_mapping" not in missing_gates:
            missing_gates.append("role_mapping")
    if not tenant_boundary_passed:
        missing_gates.append("tenant_boundary")
    if mode == "A":
        missing_gates.append("mode_a_dry_run_login_blocked")

    # Unknown role → sensitive action denial + audit
    rbac = enforce_rbac_access(
        action="final_export",
        object_type="package_export_preview",
        object_id="pkg_demo",
        resource_org_id="org_demo_sc",
        role=role_for_sensitive_check if role_for_sensitive_check else "unknown",
        organization_profile_id="org_demo_sc",
        context_kind="customer",
    )
    if not rbac.get("allowed"):
        _emit_audit(collector, "rbac_deny",
            {
                "reason": rbac.get("reason"),
                "role": role_for_sensitive_check,
                "object_type": "package_export_preview",
            },
        )

    login_live_claimed = False
    production_auth_claimed = False
    controlled_pilot_auth_ready = False

    # Even Mode B with all flags: Gate 24 default keeps claims false without
    # proven live session (no secrets in repo → never unlock)
    if (
        mode == "B"
        and provider_config_present
        and secret_present
        and invite_binding_passed
        and org_binding_passed
        and role_mapping_passed
        and rbac_handoff_passed
        and tenant_boundary_passed
        and issuer_validated
        and jwks_validated
        and audience_validated
        and callback_validated
        and session_validated
        and logout_validated
    ):
        # Eligible path — still false until real live validation lands
        login_live_claimed = False
        production_auth_claimed = False
        controlled_pilot_auth_ready = False

    _emit_audit(collector, "auth_validation_run",
        {
            "auth_validation_run_id": run_id,
            "mode": mode,
            "login_live_claimed": login_live_claimed,
        },
    )

    next_owner_action = (
        "Provide OIDC_* env out-of-band, invite/org/role bindings, "
        "NF_AUTH0_LIVE_VALIDATION_ENABLED=1; re-run Mode B without printing secrets"
        if mode == "A"
        else "Complete issuer/JWKS/audience/session live validation safely"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "auth_validation_run_id": run_id,
            "mode": mode,
            "provider_config_present": provider_config_present,
            "secret_present": secret_present_redacted,
            "live_validation_enabled": live_validation_enabled,
            "live_validation_attempted": live_validation_attempted,
            "issuer_validated": issuer_validated,
            "jwks_validated": jwks_validated,
            "audience_validated": audience_validated,
            "callback_validated": callback_validated,
            "session_validated": session_validated,
            "logout_validated": logout_validated,
            "invite_binding_passed": invite_binding_passed,
            "org_binding_passed": org_binding_passed,
            "role_mapping_passed": role_mapping_passed,
            "rbac_handoff_passed": rbac_handoff_passed,
            "tenant_boundary_passed": tenant_boundary_passed,
            "audit_event_emitted": True,
            "login_live_claimed": login_live_claimed,
            "production_auth_claimed": production_auth_claimed,
            "controlled_pilot_auth_ready": controlled_pilot_auth_ready,
            "controlled_customer_pilot_status": "NO_GO",
            "customer_data_persistence_claimed": False,
            "rbac_sensitive_denied": not bool(rbac.get("allowed")),
            "missing_gates": missing_gates,
            "next_owner_action": next_owner_action,
            "human_review_required": True,
            "fake_login_ui": False,
        }
    )


def resolve_production_auth_claim(result: dict[str, Any]) -> dict[str, Any]:
    return _json_safe(
        {
            "production_auth_claimed": False,
            "login_live_claimed": False,
            "reason": "all_gates_required_including_live_session",
            "missing_gates": result.get("missing_gates") or [],
        }
    )


def resolve_controlled_pilot_auth_readiness(result: dict[str, Any]) -> dict[str, Any]:
    ready = False
    if result.get("mode") == "A":
        ready = False
    if not result.get("invite_binding_passed"):
        ready = False
    if not result.get("org_binding_passed"):
        ready = False
    return _json_safe(
        {
            "controlled_pilot_auth_ready": ready,
            "controlled_customer_pilot_status": "NO_GO",
            "login_live_claimed": False,
        }
    )


def auth0_login_rbac_validation_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "controlled_pilot_auth_ready",
        "customer_data_persistence_claimed",
        "fake_login_ui",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("mode") == "A" and result.get("login_live_claimed"):
        fails.append("mode_a_login_live")
    if result.get("secret_present") and result.get("login_live_claimed"):
        if not result.get("session_validated"):
            fails.append("secret_alone_unlocked_login")
    return fails

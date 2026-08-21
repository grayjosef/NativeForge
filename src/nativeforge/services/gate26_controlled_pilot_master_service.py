"""Controlled pilot master resolver across auth/storage/policy/audit (Block 58)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate26_security_attestation_service import (
    build_security_attestation_contract,
)

SCHEMA_VERSION = "nf_gate26_controlled_pilot_master_v1"

STATUS_NO_GO = "NO_GO"
STATUS_CONDITIONAL_INTERNAL = "CONDITIONAL_INTERNAL_ONLY"
STATUS_READY_OWNER_REVIEW = "READY_FOR_OWNER_REVIEW"
STATUS_READY_LIMITED_EXT = "READY_FOR_LIMITED_EXTERNAL_VALIDATION"
STATUS_CONTROLLED_GO = "CONTROLLED_CUSTOMER_GO"
STATUS_PROD_ROLLOUT_NO_GO = "PRODUCTION_ROLLOUT_NO_GO"
STATUS_PROD_ROLLOUT_OWNER_REVIEW = "PRODUCTION_ROLLOUT_READY_FOR_OWNER_REVIEW"

ALLOWED_STATUSES = (
    STATUS_NO_GO,
    STATUS_CONDITIONAL_INTERNAL,
    STATUS_READY_OWNER_REVIEW,
    STATUS_READY_LIMITED_EXT,
    STATUS_CONTROLLED_GO,
    STATUS_PROD_ROLLOUT_NO_GO,
    STATUS_PROD_ROLLOUT_OWNER_REVIEW,
)

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(event: str, detail: dict[str, Any]) -> None:
    _AUDIT.append({"event": event, **detail})


def resolve_controlled_pilot_master(
    *,
    # Auth
    auth0_config_present: bool = False,
    login_live: bool = False,
    production_auth_claim: bool = False,
    external_user_access_claim: bool = False,
    rbac_enforced_scope: bool = True,
    tenant_boundary_status: str = "enforced_model",
    session_enforcement_status: str = "dry_run",
    # Storage
    storage_approval_present: bool = False,
    storage_approval_valid: bool = False,
    production_metadata_status: str = "blocked",
    production_object_storage_status: str = "blocked",
    signed_url_status: str = "blocked",
    sse_encryption_status: str = "not_configured",
    malware_scan_status: str = "unsatisfied",
    production_storage_claim: bool = False,
    # Policy
    customer_data_policy_status: str = "policy_required",
    ai_training_consent_default: bool = False,
    retention_delete_export_status: str = "production_blocked",
    customer_persistence_claim: bool = False,
    # Security
    sca_status: str = "passed_gate16",
    pen_test_status: str = "no_report",
    security_attestation_status: str = "no_report",
    pen_test_passed: bool = False,
    allow_limited_external_without_pentest: bool = False,
    # Product
    authority_verification_status: str = "not_live",
    source_coverage_status: str = "not_live",
    invite_readiness: bool = False,
    operator_support_status: str = "ready_internal",
    ux_readiness_status: str = "monday_demo_go",
    customer_feedback_path_status: str = "modeled",
    persistence_required_for_pilot: bool = True,
) -> dict[str, Any]:
    missing: list[str] = []
    forbidden: list[str] = []
    allowed: list[str] = []

    if not auth0_config_present:
        missing.append("auth0_config")
    if not login_live:
        missing.append("login_live")
    if not production_auth_claim:
        missing.append("production_auth")
    if not external_user_access_claim:
        missing.append("external_user_access")
    if not rbac_enforced_scope:
        missing.append("rbac")
    if tenant_boundary_status in {"failed", "unknown", ""}:
        missing.append("tenant_boundary")
    if session_enforcement_status in {"invalid", "expired", "unknown"}:
        missing.append("session_enforcement")

    if not storage_approval_present or not storage_approval_valid:
        missing.append("storage_approval")
    if production_metadata_status != "validated":
        missing.append("production_metadata")
    if production_object_storage_status != "validated":
        missing.append("production_object_storage")
    if signed_url_status != "live_validated":
        missing.append("signed_url")
    if sse_encryption_status != "configured":
        missing.append("sse_encryption")
    if malware_scan_status != "satisfied":
        missing.append("malware_scan")
    if not production_storage_claim:
        missing.append("production_storage")

    if customer_data_policy_status not in {
        "approved_for_controlled_pilot",
        "approved_for_production",
    }:
        missing.append("customer_data_policy")
    if ai_training_consent_default is not False:
        missing.append("ai_training_default_not_false")
    if not customer_persistence_claim and persistence_required_for_pilot:
        missing.append("customer_persistence")

    if sca_status not in {"passed_gate16", "passed"}:
        missing.append("sca")
    if not pen_test_passed:
        missing.append("pen_test")
    if security_attestation_status in {"no_report", "blocked", "unknown"}:
        if "pen_test" not in missing:
            missing.append("security_attestation")

    if authority_verification_status != "live":
        missing.append("authority_live")
        forbidden.append("final_eligibility_claim")
        forbidden.append("submission_ready_claim")
    if source_coverage_status != "live":
        missing.append("source_coverage_live")
        forbidden.append("broad_coverage_claim")
    if not invite_readiness:
        missing.append("invite_readiness")
    if operator_support_status not in {"ready_internal", "ready"}:
        missing.append("operator_support")

    # Hard blocks for CONTROLLED_CUSTOMER_GO
    blocks_go: list[str] = []
    if not login_live:
        blocks_go.append("login_live=false")
    if not production_auth_claim:
        blocks_go.append("production_auth=false")
    if persistence_required_for_pilot and not production_storage_claim:
        blocks_go.append("production_storage=false")
    if persistence_required_for_pilot and not customer_persistence_claim:
        blocks_go.append("customer_persistence=false")
    if not pen_test_passed and not allow_limited_external_without_pentest:
        blocks_go.append("pen_test_passed=false")

    # Status resolution — Mode A truthful default
    pilot_status = STATUS_CONDITIONAL_INTERNAL
    reason = "Internal/demo scaffolding OK; external auth/storage/pen-test incomplete"

    if blocks_go:
        if sca_status in {"passed_gate16", "passed"} and rbac_enforced_scope:
            pilot_status = STATUS_CONDITIONAL_INTERNAL
        else:
            pilot_status = STATUS_NO_GO
            reason = "Core security/SCA/RBAC incomplete"

    # Limited external validation only if policy explicitly allows AND login+auth ok
    if (
        allow_limited_external_without_pentest
        and login_live
        and production_auth_claim
        and not pen_test_passed
    ):
        pilot_status = STATUS_READY_LIMITED_EXT
        reason = "Limited external validation policy; pen-test still required for GO"

    # READY_FOR_OWNER_REVIEW when most gates true except owner stamp
    if (
        login_live
        and production_auth_claim
        and production_storage_claim
        and customer_persistence_claim
        and pen_test_passed
        and authority_verification_status == "live"
        and not invite_readiness
    ):
        pilot_status = STATUS_READY_OWNER_REVIEW
        reason = "Core gates green; invite/owner review remaining"

    # CONTROLLED_CUSTOMER_GO only if zero blocks and no missing critical gates
    if not blocks_go and len(missing) == 0:
        pilot_status = STATUS_CONTROLLED_GO
        reason = "All required gates passed"

    # Safety clamp: Mode A defaults never unlock GO
    if pilot_status == STATUS_CONTROLLED_GO and blocks_go:
        pilot_status = STATUS_NO_GO
        reason = "Safety clamp — controlled GO blocked by hard gates"

    # Production rollout — always NO_GO unless every production gate
    production_rollout_status = STATUS_PROD_ROLLOUT_NO_GO
    if (
        pilot_status == STATUS_CONTROLLED_GO
        and production_storage_claim
        and pen_test_passed
        and login_live
    ):
        production_rollout_status = STATUS_PROD_ROLLOUT_OWNER_REVIEW
    # Gate 26: still keep production rollout NO_GO in practice for Mode A
    if not (
        login_live
        and production_auth_claim
        and production_storage_claim
        and customer_persistence_claim
        and pen_test_passed
    ):
        production_rollout_status = STATUS_PROD_ROLLOUT_NO_GO

    allowed.extend(
        [
            "monday_demo_internal_go",
            "conditional_internal_only",
            "security_attestation_model_exists",
            "pilot_master_resolver_exists",
            "sca_gate16_pass_preserved",
        ]
    )
    if ai_training_consent_default is False:
        allowed.append("ai_training_consent_default_false")

    forbidden.extend(
        [
            "controlled_customer_pilot_go",
            "production_rollout_go",
            "production_ready",
            "pen_test_passed",
            "login_live",
            "production_auth",
            "production_storage",
            "customer_persistence",
            "no_findings",
        ]
    )
    # Deduplicate
    forbidden = sorted(set(forbidden))
    allowed = sorted(set(allowed))

    _emit_audit(
        "controlled_pilot_master_resolve",
        {
            "pilot_status": pilot_status,
            "production_rollout_status": production_rollout_status,
            "missing_count": len(missing),
        },
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "master_resolver": True,
            "auth_gate": {
                "auth0_config_present": auth0_config_present,
                "login_live": login_live,
                "production_auth_claim": production_auth_claim,
                "external_user_access_claim": external_user_access_claim,
                "rbac_enforced_scope": rbac_enforced_scope,
                "tenant_boundary_status": tenant_boundary_status,
                "session_enforcement_status": session_enforcement_status,
            },
            "storage_gate": {
                "storage_approval_present": storage_approval_present,
                "storage_approval_valid": storage_approval_valid,
                "production_metadata_status": production_metadata_status,
                "production_object_storage_status": production_object_storage_status,
                "signed_url_status": signed_url_status,
                "sse_encryption_status": sse_encryption_status,
                "malware_scan_status": malware_scan_status,
                "production_storage_claim": production_storage_claim,
            },
            "customer_data_policy_gate": {
                "customer_data_policy_status": customer_data_policy_status,
                "ai_training_consent_default": ai_training_consent_default,
                "retention_delete_export_status": retention_delete_export_status,
                "customer_persistence_claim": customer_persistence_claim,
            },
            "tenant_session_rbac_gate": {
                "rbac_enforced_scope": rbac_enforced_scope,
                "tenant_boundary_status": tenant_boundary_status,
                "session_enforcement_status": session_enforcement_status,
            },
            "sca_gate": sca_status,
            "pen_test_gate": {
                "pen_test_status": pen_test_status,
                "security_attestation_status": security_attestation_status,
                "pen_test_passed": pen_test_passed,
            },
            "authority_gate": authority_verification_status,
            "source_coverage_gate": source_coverage_status,
            "invite_support_gate": {
                "invite_readiness": invite_readiness,
                "operator_support_status": operator_support_status,
                "customer_feedback_path_status": customer_feedback_path_status,
            },
            "ux_readiness_gate": ux_readiness_status,
            "controlled_customer_pilot_status": pilot_status,
            "production_rollout_status": production_rollout_status,
            "reason": reason,
            "blocks_go": blocks_go,
            "allowed_claims": allowed,
            "forbidden_claims": forbidden,
            "missing_gates": missing,
            "allowed_statuses": list(ALLOWED_STATUSES),
            "fake_pilot_ready_banner": False,
            "fake_secure_badge": False,
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "production_storage_claimed": False,
            "customer_persistence_claimed": False,
            "pen_test_passed_claimed": False,
            "next_owner_actions": [
                "Provide Auth0/OIDC config and complete live login validation",
                "Provide storage approval + metadata/object/SSE/malware config",
                "Commission pen-test and attach evidence for Gate 26 Mode B",
                "Approve customer data policy before any persistence claim",
            ],
            "human_review_required": True,
        }
    )


def resolve_production_rollout(master: dict[str, Any]) -> dict[str, Any]:
    return _json_safe(
        {
            "production_rollout_status": master.get("production_rollout_status")
            or STATUS_PROD_ROLLOUT_NO_GO,
            "production_ready_claimed": False,
        }
    )


def build_mode_a_pilot_master_packet() -> dict[str, Any]:
    attestation = build_security_attestation_contract()
    master = resolve_controlled_pilot_master(
        pen_test_status=attestation.get("evidence_status") or "no_report",
        security_attestation_status=attestation.get("evidence_status") or "no_report",
        pen_test_passed=False,
        sca_status="passed_gate16",
        ai_training_consent_default=False,
    )
    return _json_safe(
        {
            "attestation": attestation,
            "master": master,
            "production_rollout": resolve_production_rollout(master),
        }
    )


def controlled_pilot_master_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "fake_pilot_ready_banner",
        "fake_secure_badge",
        "login_live_claimed",
        "production_auth_claimed",
        "production_storage_claimed",
        "customer_persistence_claimed",
        "pen_test_passed_claimed",
    ):
        if result.get(key) is True:
            fails.append(key)
    status = result.get("controlled_customer_pilot_status")
    if status == STATUS_CONTROLLED_GO:
        # Only OK if no missing/blocks — Mode A tests must not hit this
        if result.get("missing_gates") or result.get("blocks_go"):
            fails.append("go_with_missing_gates")
    if result.get("production_rollout_status") not in {
        STATUS_PROD_ROLLOUT_NO_GO,
        STATUS_PROD_ROLLOUT_OWNER_REVIEW,
    }:
        if result.get("production_rollout_status") == "GO":
            fails.append("rollout_go")
    return fails


def get_controlled_pilot_master_audit() -> list[dict[str, Any]]:
    return list(_AUDIT)


def clear_controlled_pilot_master_audit_for_tests() -> None:
    _AUDIT.clear()

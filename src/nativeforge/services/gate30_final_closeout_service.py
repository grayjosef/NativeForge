"""Final pilot GO/NO-GO resolver + 3000-sprint production-grade closeout (Block 65)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.gate26_controlled_pilot_master_service import (
    STATUS_CONDITIONAL_INTERNAL,
    STATUS_CONTROLLED_GO,
    STATUS_NO_GO,
    STATUS_PROD_ROLLOUT_NO_GO,
    STATUS_PROD_ROLLOUT_OWNER_REVIEW,
    STATUS_READY_LIMITED_EXT,
    STATUS_READY_OWNER_REVIEW,
    resolve_controlled_pilot_master,
)
from nativeforge.services.gate27_cutover_claim_freeze_service import (
    build_claim_freeze_matrix,
)

SCHEMA_VERSION = "nf_gate30_final_closeout_v1"

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(event: str, detail: dict[str, Any]) -> None:
    _AUDIT.append({"event": event, **detail})


def resolve_final_pilot_packet(
    *,
    auth0_config_present: bool = False,
    login_live: bool = False,
    production_auth: bool = False,
    external_user_access: bool = False,
    rbac_scope: bool = True,
    tenant_boundary: str = "enforced_model",
    session_enforcement: str = "dry_run",
    storage_approval: bool = False,
    production_metadata: str = "blocked",
    production_object_storage: str = "blocked",
    signed_url_status: str = "blocked",
    sse_encryption: str = "not_configured",
    malware_scan: str = "unsatisfied",
    customer_data_policy: str = "policy_required",
    retention_delete_export: str = "production_blocked",
    customer_persistence: bool = False,
    sca_status: str = "passed_gate16",
    pen_test_status: str = "no_report",
    pen_test_passed: bool = False,
    allow_limited_external_without_pentest: bool = False,
    authority_status: str = "not_live",
    source_coverage_status: str = "not_live",
    invite_readiness: bool = False,
    support_readiness: str = "ready_internal",
    feedback_path: str = "modeled",
    ux_readiness: str = "monday_demo_go",
    claim_freeze_status: str = "verified",
    production_storage: bool = False,
) -> dict[str, Any]:
    master = resolve_controlled_pilot_master(
        auth0_config_present=auth0_config_present,
        login_live=login_live,
        production_auth_claim=production_auth,
        external_user_access_claim=external_user_access,
        rbac_enforced_scope=rbac_scope,
        tenant_boundary_status=tenant_boundary,
        session_enforcement_status=session_enforcement,
        storage_approval_present=storage_approval,
        storage_approval_valid=storage_approval,
        production_metadata_status=production_metadata,
        production_object_storage_status=production_object_storage,
        signed_url_status=signed_url_status,
        sse_encryption_status=sse_encryption,
        malware_scan_status=malware_scan,
        production_storage_claim=production_storage,
        customer_data_policy_status=customer_data_policy,
        retention_delete_export_status=retention_delete_export,
        customer_persistence_claim=customer_persistence,
        sca_status=sca_status,
        pen_test_status=pen_test_status,
        pen_test_passed=pen_test_passed,
        allow_limited_external_without_pentest=allow_limited_external_without_pentest,
        authority_verification_status=authority_status,
        source_coverage_status=source_coverage_status,
        invite_readiness=invite_readiness,
        operator_support_status=support_readiness,
        ux_readiness_status=ux_readiness,
        customer_feedback_path_status=feedback_path,
        persistence_required_for_pilot=True,
    )
    freeze = build_claim_freeze_matrix()

    blocks_go: list[str] = []
    if not login_live:
        blocks_go.append("login_live=false")
    if not production_auth:
        blocks_go.append("production_auth=false")
    if not production_storage:
        blocks_go.append("production_storage=false")
    if not customer_persistence:
        blocks_go.append("customer_persistence=false")
    if not pen_test_passed and not allow_limited_external_without_pentest:
        blocks_go.append("pen_test_passed=false")

    forbidden_with_reason = [
        {
            "claim": "controlled_customer_pilot_go",
            "reason": "hard gates missing" if blocks_go else "owner review remaining",
            "missing_evidence": blocks_go or ["owner_stamp"],
        },
        {
            "claim": "production_rollout_go",
            "reason": "production rollout stays NO_GO while any hard gate is missing",
            "missing_evidence": blocks_go or ["owner_rollout_review"],
        },
        {
            "claim": "production_ready",
            "reason": "not validated",
            "missing_evidence": ["production_cutover_executed"],
        },
        {
            "claim": "login_live",
            "reason": "Auth0 live validation not passed",
            "missing_evidence": ["OIDC_OOB", "callback_session"],
        },
        {
            "claim": "production_auth",
            "reason": "production auth not validated",
            "missing_evidence": ["invite_org_role", "rbac_live"],
        },
        {
            "claim": "production_storage",
            "reason": "approval/config/provisioning incomplete",
            "missing_evidence": ["storage_approval", "metadata_object_sse_malware"],
        },
        {
            "claim": "customer_persistence",
            "reason": "policy + auth + storage + tenant + audit incomplete",
            "missing_evidence": [
                "customer_data_policy",
                "login_live",
                "production_storage",
            ],
        },
        {
            "claim": "pen_test_passed",
            "reason": "no real report/pass evidence",
            "missing_evidence": ["pen_test_report"],
        },
        {
            "claim": "final_eligibility",
            "reason": "authority_not_live blocks final eligibility/submission claims",
            "missing_evidence": ["authority_live"],
        },
        {
            "claim": "submission_ready",
            "reason": "authority_not_live blocks submission claims",
            "missing_evidence": ["authority_live"],
        },
        {
            "claim": "broad_coverage",
            "reason": "source_coverage_not_live blocks broad coverage claims",
            "missing_evidence": ["source_coverage_live"],
        },
        {
            "claim": "mode_b_executed",
            "reason": "real owner inputs absent",
            "missing_evidence": ["real_auth0", "real_storage", "real_pen_test"],
        },
    ]
    if authority_status == "live":
        forbidden_with_reason = [
            x
            for x in forbidden_with_reason
            if x["claim"] not in {"final_eligibility", "submission_ready"}
        ]
    if source_coverage_status == "live":
        forbidden_with_reason = [
            x for x in forbidden_with_reason if x["claim"] != "broad_coverage"
        ]

    allowed_with_evidence = [
        {
            "claim": "monday_demo_go",
            "evidence": "sc_customer_demo route + Playwright smoke",
        },
        {
            "claim": "conditional_internal_only",
            "evidence": "Gate 26/30 resolver default",
        },
        {
            "claim": "sca_gate16_pass",
            "evidence": "Gate 16 SCA evidence (deps unchanged)",
        },
        {
            "claim": "real_input_detectors_exist",
            "evidence": "Gate 29 ingest services",
        },
        {
            "claim": "claim_freeze_verified",
            "evidence": freeze.get("schema_version"),
        },
        {
            "claim": "dry_run_cutover_exists",
            "evidence": "Gate 28 22-step dry-run",
        },
    ]

    pilot_status = master.get("controlled_customer_pilot_status")
    if blocks_go and pilot_status == STATUS_CONTROLLED_GO:
        pilot_status = STATUS_NO_GO
    if not blocks_go and not master.get("missing_gates"):
        # Still require every listed input true for GO
        pilot_status = STATUS_CONTROLLED_GO
    if blocks_go:
        if sca_status in {"passed_gate16", "passed"} and rbac_scope:
            if (
                allow_limited_external_without_pentest
                and login_live
                and production_auth
            ):
                if "pen_test_passed=false" in blocks_go and len(blocks_go) == 1:
                    pilot_status = STATUS_READY_LIMITED_EXT
                else:
                    pilot_status = STATUS_CONDITIONAL_INTERNAL
            else:
                pilot_status = STATUS_CONDITIONAL_INTERNAL
        else:
            pilot_status = STATUS_NO_GO

    rollout = STATUS_PROD_ROLLOUT_NO_GO
    if (
        not blocks_go
        and login_live
        and production_auth
        and production_storage
        and customer_persistence
        and pen_test_passed
    ):
        rollout = STATUS_PROD_ROLLOUT_OWNER_REVIEW
        # Gate 30 still does not claim production rollout GO
    if blocks_go:
        rollout = STATUS_PROD_ROLLOUT_NO_GO

    owner_actions = [
        {
            "unlocks": "login_live / production_auth",
            "action": "Provide OIDC_* OOB; enable live validation; pass callback/session",
        },
        {
            "unlocks": "production_storage",
            "action": "Repo-safe storage approval + OOB metadata/object/SSE/malware",
        },
        {
            "unlocks": "customer_persistence",
            "action": "Approve customer data policy after auth+storage+tenant+audit",
        },
        {
            "unlocks": "pen_test_passed",
            "action": "Attach real pen-test report with closed critical/high",
        },
        {
            "unlocks": "controlled_customer_pilot_go",
            "action": "All hard gates above plus invite/authority/coverage live",
        },
        {
            "unlocks": "production_rollout_review",
            "action": "Controlled GO plus owner rollout review — still not auto GO",
        },
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "final_pilot_resolver": True,
            "final_production_rollout_resolver": True,
            "final_claim_freeze": True,
            "controlled_customer_pilot_status": pilot_status,
            "production_rollout_status": rollout,
            "blocks_go": blocks_go,
            "allowed_claims": [x["claim"] for x in allowed_with_evidence],
            "forbidden_claims": [x["claim"] for x in forbidden_with_reason],
            "allowed_claims_with_evidence": allowed_with_evidence,
            "forbidden_claims_with_reason": forbidden_with_reason,
            "claim_freeze_status": claim_freeze_status,
            "frozen_claim_booleans": freeze.get("frozen_claim_booleans"),
            "master": master,
            "status_enum": [
                STATUS_NO_GO,
                STATUS_CONDITIONAL_INTERNAL,
                STATUS_READY_OWNER_REVIEW,
                STATUS_READY_LIMITED_EXT,
                STATUS_CONTROLLED_GO,
                STATUS_PROD_ROLLOUT_NO_GO,
                STATUS_PROD_ROLLOUT_OWNER_REVIEW,
            ],
            "owner_action_matrix": owner_actions,
            "login_live_claimed": False if not login_live else True,
            "production_auth_claimed": False if not production_auth else True,
            "production_storage_claimed": False if not production_storage else True,
            "customer_persistence_claimed": False if not customer_persistence else True,
            "pen_test_passed_claimed": False if not pen_test_passed else True,
            "mode_b_executed_claimed": False,
            "fake_pilot_ready": False,
            "fake_production_ready": False,
        }
    )


def build_3000_sprint_closeout() -> dict[str, Any]:
    run_id = (
        f"nf_gate30_closeout_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    packet = resolve_final_pilot_packet()
    evidence_map = {
        "discovery_engine": "campaign blocks 01–02",
        "eligibility_recognition": "campaign eligibility services",
        "monday_demo": "/?view=sc_customer_demo",
        "auth_model": "Gates 24/27/29",
        "storage_model": "Gates 25/27/29",
        "policy_model": "Gate 23",
        "security_attestation": "Gate 26",
        "cutover_dry_run": "Gate 28",
        "real_input_ingest": "Gate 29",
        "sca": "Gate 16 evidence",
    }
    blocker_map = [
        {"blocker": "Auth0/OIDC OOB absent", "blocks": "login_live"},
        {"blocker": "storage approval/config absent", "blocks": "production_storage"},
        {"blocker": "pen-test report absent", "blocks": "pen_test_passed"},
        {"blocker": "authority not live", "blocks": "final_eligibility"},
        {"blocker": "source coverage not live", "blocks": "broad_coverage"},
    ]
    answers = {
        "1_built": (
            "Native-relevant grant discovery + intelligence, Monday demo, "
            "auth/storage/policy/security models, ingest/cutover rehearsal"
        ),
        "2_validated": "Scoped tests/smokes/Playwright; Gate 16 SCA; claim freeze",
        "3_owner_blocked": "Real Auth0, storage provision, pen-test evidence",
        "4_monday_claims": packet["allowed_claims"],
        "5_internal_pilot": STATUS_CONDITIONAL_INTERNAL,
        "6_cannot_claim_customer_pilot": packet["forbidden_claims"],
        "7_owner_mode_b": packet["owner_action_matrix"],
        "8_before_customer_access": packet["blocks_go"],
        "9_unlock_customer_go": "Zero hard-gate blocks + live authority/coverage/invite",
        "10_unlock_rollout_review": "Controlled GO plus owner rollout review (still not GO)",
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "closeout_run_id": run_id,
        "campaign": "3000-sprint production-grade conversion",
        "mode": "A",
        "final_pilot_resolver": True,
        "final_production_rollout_resolver": True,
        "final_claim_freeze": True,
        "evidence_map": evidence_map,
        "blocker_map": blocker_map,
        "owner_action_matrix": packet["owner_action_matrix"],
        "capability_index": list(evidence_map.keys()),
        "risk_register": [
            "false production claim",
            "synthetic treated as real",
            "customer data before persistence gates",
        ],
        "security_posture_summary": (
            "SCA Gate 16 preserved; pen-test not passed; Auth0 not live"
        ),
        "ux_readiness_summary": "Monday demo GO; buyer trust surfaces Gate 30",
        "controlled_customer_pilot_status": packet["controlled_customer_pilot_status"],
        "production_rollout_status": packet["production_rollout_status"],
        "allowed_claims": packet["allowed_claims"],
        "forbidden_claims": packet["forbidden_claims"],
        "allowed_claims_with_evidence": packet["allowed_claims_with_evidence"],
        "forbidden_claims_with_reason": packet["forbidden_claims_with_reason"],
        "login_live_claimed": False,
        "production_auth_claimed": False,
        "production_storage_claimed": False,
        "customer_persistence_claimed": False,
        "pen_test_passed_claimed": False,
        "mode_b_executed_claimed": False,
        "fake_pilot_ready": False,
        "fake_production_ready": False,
        "answers": answers,
        "packet": packet,
        "next_owner_action": (
            "Provide real OIDC_* OOB, storage approval/config, and pen-test report"
        ),
        "human_review_required": True,
        "prompt_alone_is_not_approval": True,
    }
    _emit_audit("gate30_closeout", {"run_id": run_id, "mode": "A"})
    return _json_safe(result)


def final_closeout_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("mode") == "A":
        for key in (
            "login_live_claimed",
            "production_auth_claimed",
            "production_storage_claimed",
            "customer_persistence_claimed",
            "pen_test_passed_claimed",
            "mode_b_executed_claimed",
            "fake_pilot_ready",
            "fake_production_ready",
        ):
            if result.get(key) is True:
                fails.append(key)
        if result.get("controlled_customer_pilot_status") == STATUS_CONTROLLED_GO:
            fails.append("pilot_go")
        if (
            result.get("production_rollout_status")
            not in {
                STATUS_PROD_ROLLOUT_NO_GO,
                None,
            }
            and result.get("production_rollout_status") == "GO"
        ):
            fails.append("rollout_go")
        if result.get("production_rollout_status") != STATUS_PROD_ROLLOUT_NO_GO:
            fails.append("rollout_not_nogo")
    allowed = result.get("allowed_claims_with_evidence") or []
    if any(not x.get("evidence") for x in allowed):
        fails.append("allowed_without_evidence")
    forbidden = result.get("forbidden_claims_with_reason") or []
    if any(not (x.get("reason") or x.get("missing_evidence")) for x in forbidden):
        fails.append("forbidden_without_reason")
    return fails


def get_final_closeout_audit() -> list[dict[str, Any]]:
    return list(_AUDIT)


def clear_final_closeout_audit_for_tests() -> None:
    _AUDIT.clear()

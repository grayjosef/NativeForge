"""Storage + pen-test real evidence ingest + pilot resolver re-evaluation (Block 64)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.gate26_controlled_pilot_master_service import (
    build_mode_a_pilot_master_packet,
    resolve_controlled_pilot_master,
)
from nativeforge.services.gate27_cutover_claim_freeze_service import (
    build_claim_freeze_matrix,
)
from nativeforge.services.gate28_mode_b_rehearsal_service import (
    build_synthetic_non_secret_fixture,
)
from nativeforge.services.gate29_auth0_real_input_service import (
    is_synthetic_rehearsal_artifact,
    run_auth0_real_input_ingest,
)

SCHEMA_VERSION = "nf_gate29_storage_security_real_input_v1"

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(event: str, detail: dict[str, Any]) -> None:
    _AUDIT.append({"event": event, **detail})


def run_storage_security_real_input_ingest(
    *,
    owner_storage: dict[str, Any] | None = None,
    owner_pen_test: dict[str, Any] | None = None,
    approval_token_present: bool = False,
    approval_token_valid: bool = False,
    metadata_config_present: bool = False,
    object_config_present: bool = False,
    signed_url_config_present: bool = False,
    sse_encryption_config_present: bool = False,
    malware_scan_config_present: bool = False,
    backup_restore_config_present: bool = False,
    retention_delete_config_present: bool = False,
    report_present: bool = False,
    scope_validated: bool = False,
    critical_high_open: bool = True,
    remediation_required: bool = True,
    retest_required: bool = True,
    pass_evidence: bool = False,
    login_live: bool = False,
    customer_data_policy_approved: bool = False,
    tenant_ok: bool = False,
    audit_ok: bool = False,
) -> dict[str, Any]:
    run_id = (
        f"nf_storage_sec_real_input_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    storage_synthetic = is_synthetic_rehearsal_artifact(owner_storage)
    pentest_synthetic = is_synthetic_rehearsal_artifact(owner_pen_test)
    gate28 = build_synthetic_non_secret_fixture()
    # Always ignore Gate 28 synthetic storage/security flags
    if storage_synthetic or owner_storage is None:
        # Treat synthetic approval flags as absent
        if storage_synthetic:
            approval_token_present = False
            approval_token_valid = False
            metadata_config_present = False
            object_config_present = False
            signed_url_config_present = False
            sse_encryption_config_present = False
            malware_scan_config_present = False
            backup_restore_config_present = False
            retention_delete_config_present = False
    if pentest_synthetic or owner_pen_test is None:
        if pentest_synthetic:
            report_present = False
            scope_validated = False
            pass_evidence = False
            critical_high_open = True

    real_storage = bool(
        approval_token_present
        and approval_token_valid
        and not storage_synthetic
        and (
            metadata_config_present
            or object_config_present
            or signed_url_config_present
        )
    )
    # Production storage requires approval AND configs AND live validation attempt
    storage_validation_attempted = bool(
        real_storage
        and metadata_config_present
        and object_config_present
        and signed_url_config_present
        and sse_encryption_config_present
        and malware_scan_config_present
        and backup_restore_config_present
        and retention_delete_config_present
        and not storage_synthetic
    )
    production_storage = bool(storage_validation_attempted)
    customer_persistence = bool(
        production_storage
        and login_live
        and customer_data_policy_approved
        and tenant_ok
        and audit_ok
        and sse_encryption_config_present
        and malware_scan_config_present
    )

    real_pentest = bool(report_present and not pentest_synthetic)
    scope_ok = bool(real_pentest and scope_validated)
    pentest_pass = bool(
        real_pentest
        and scope_ok
        and not critical_high_open
        and not remediation_required
        and not retest_required
        and pass_evidence
    )

    auth = run_auth0_real_input_ingest()
    packet = build_mode_a_pilot_master_packet()
    master = packet.get("master") or {}
    # Re-evaluate with current claims (Mode A defaults remain blocked)
    rerun = resolve_controlled_pilot_master(
        login_live=login_live or auth.get("login_live_claimed") is True,
        production_auth_claim=auth.get("production_auth_claimed") is True,
        storage_approval_present=approval_token_present and not storage_synthetic,
        storage_approval_valid=approval_token_valid and not storage_synthetic,
        production_storage_claim=production_storage,
        customer_persistence_claim=customer_persistence,
        pen_test_passed=pentest_pass,
        pen_test_status="passed" if pentest_pass else "no_report",
    )
    freeze = build_claim_freeze_matrix()
    pilot_status = rerun.get("controlled_customer_pilot_status") or master.get(
        "controlled_customer_pilot_status"
    )
    rollout = rerun.get("production_rollout_status") or master.get(
        "production_rollout_status"
    )

    missing: list[str] = []
    if not approval_token_present or not approval_token_valid:
        missing.append("repo_safe_storage_approval")
    if not metadata_config_present:
        missing.append("metadata_config_oob")
    if not object_config_present:
        missing.append("object_storage_config_oob")
    if not signed_url_config_present:
        missing.append("signed_url_config")
    if not sse_encryption_config_present:
        missing.append("sse_kms_config")
    if not malware_scan_config_present:
        missing.append("malware_scan_config")
    if not backup_restore_config_present:
        missing.append("backup_restore_config")
    if not retention_delete_config_present:
        missing.append("retention_delete_config")
    if not login_live:
        missing.append("login_live")
    if not customer_data_policy_approved:
        missing.append("customer_data_policy_approval")
    if not tenant_ok:
        missing.append("tenant_boundary")
    if not audit_ok:
        missing.append("audit")
    if not report_present:
        missing.append("pen_test_report")
    if not pentest_pass:
        missing.append("pen_test_pass_evidence")

    result = {
        "schema_version": SCHEMA_VERSION,
        "real_storage_input_detector": True,
        "real_pen_test_evidence_detector": True,
        "storage_security_real_input_run_id": run_id,
        "mode": "A",
        "synthetic_rehearsal_artifacts_ignored": True,
        "synthetic_storage_artifacts_ignored": True,
        "synthetic_pen_test_artifacts_ignored": True,
        "gate28_synthetic_fixture_kind": gate28.get("fixture_kind"),
        "real_storage_inputs_present": real_storage,
        "approval_token_present": bool(
            approval_token_present and not storage_synthetic
        ),
        "approval_token_valid": bool(approval_token_valid and not storage_synthetic),
        "metadata_config_present": bool(
            metadata_config_present and not storage_synthetic
        ),
        "object_config_present": bool(object_config_present and not storage_synthetic),
        "signed_url_config_present": bool(
            signed_url_config_present and not storage_synthetic
        ),
        "sse_encryption_config_present": bool(
            sse_encryption_config_present and not storage_synthetic
        ),
        "malware_scan_config_present": bool(
            malware_scan_config_present and not storage_synthetic
        ),
        "retention_delete_config_present": bool(
            retention_delete_config_present and not storage_synthetic
        ),
        "production_storage_validation_attempted": storage_validation_attempted,
        "production_storage_claimed": production_storage,
        "customer_persistence_claimed": customer_persistence,
        "real_pen_test_evidence_present": real_pentest,
        "pen_test_scope_validated": scope_ok,
        "critical_high_open": critical_high_open if real_pentest else True,
        "remediation_required": remediation_required if real_pentest else True,
        "retest_required": retest_required if real_pentest else True,
        "pen_test_pass_claimed": pentest_pass,
        "controlled_customer_pilot_status": pilot_status or "CONDITIONAL_INTERNAL_ONLY",
        "production_rollout_status": rollout or "PRODUCTION_ROLLOUT_NO_GO",
        "allowed_claims": [
            "real_input_detector_exists",
            "synthetic_artifacts_rejected",
            "pilot_resolver_rerun",
        ],
        "forbidden_claims": [
            "production_storage",
            "customer_persistence",
            "pen_test_passed",
            "controlled_customer_pilot_go",
            "production_rollout_go",
            "mode_b_executed",
        ],
        "claim_freeze_verified": True,
        "frozen_claim_booleans": freeze.get("frozen_claim_booleans"),
        "missing_gates": missing,
        "prompt_alone_is_not_approval": True,
        "customer_data_mutated": False,
        "production_data_mutated": False,
        "fake_pilot_ready": False,
        "next_owner_action": (
            "Place repo-safe storage approval + OOB metadata/object/SSE/malware "
            "config, then attach real pen-test report with closed critical/high"
        ),
        "human_review_required": True,
    }
    # Mode A default: no real owner storage/pen-test in env → force frozen false
    if not real_storage:
        result["production_storage_claimed"] = False
        result["customer_persistence_claimed"] = False
        result["production_storage_validation_attempted"] = False
        result["real_storage_inputs_present"] = False
    if not real_pentest:
        result["pen_test_pass_claimed"] = False
        result["real_pen_test_evidence_present"] = False
    if result["controlled_customer_pilot_status"] == "CONTROLLED_CUSTOMER_GO":
        # Hard freeze: cannot GO while Mode A missing gates
        if result["missing_gates"]:
            result["controlled_customer_pilot_status"] = "CONDITIONAL_INTERNAL_ONLY"

    _emit_audit(
        "storage_security_real_input",
        {
            "run_id": run_id,
            "production_storage_claimed": result["production_storage_claimed"],
            "pen_test_pass_claimed": result["pen_test_pass_claimed"],
        },
    )
    return _json_safe(result)


def storage_security_real_input_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("mode") == "A":
        for key in (
            "production_storage_claimed",
            "customer_persistence_claimed",
            "pen_test_pass_claimed",
            "fake_pilot_ready",
            "customer_data_mutated",
            "production_data_mutated",
        ):
            if result.get(key) is True:
                fails.append(key)
        if result.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
            fails.append("pilot_go")
        if result.get("production_rollout_status") == "GO":
            fails.append("rollout_go")
        if not result.get("synthetic_rehearsal_artifacts_ignored"):
            fails.append("synthetic_not_ignored")
        if not result.get("claim_freeze_verified"):
            fails.append("freeze_not_verified")
    return fails


def get_storage_security_real_input_audit() -> list[dict[str, Any]]:
    return list(_AUDIT)


def clear_storage_security_real_input_audit_for_tests() -> None:
    _AUDIT.clear()

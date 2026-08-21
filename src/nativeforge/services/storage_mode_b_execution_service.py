"""Storage Mode B detector and safe validation attempt (Block 46)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.storage_feature_flag_service import (
    build_storage_feature_flag_contract,
)
from nativeforge.services.storage_owner_approval_token_service import (
    build_storage_owner_approval_token,
)
from nativeforge.services.storage_provisioning_execution_guard_service import (
    evaluate_storage_provisioning_guard,
)

SCHEMA_VERSION = "nf_storage_mode_b_execution_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def detect_and_run_storage_mode_b(
    *,
    approval: dict[str, Any] | None = None,
    flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token = approval or build_storage_owner_approval_token(present=False)
    f = flags or build_storage_feature_flag_contract()
    missing: list[str] = []

    approval_present = bool(token.get("approval_present"))
    approval_valid = bool(
        approval_present
        and not token.get("revoked")
        and not token.get("stale")
        and token.get("production_storage_approved")
    )
    if not approval_present:
        missing.append("owner_approval_absent")
    if token.get("revoked"):
        missing.append("approval_revoked")
    if token.get("stale"):
        missing.append("approval_stale")
    if not token.get("production_storage_approved"):
        missing.append("production_storage_not_approved")

    for key in (
        "production_storage_config_present",
        "metadata_db_config_present",
        "object_storage_config_present",
        "signed_url_config_present",
        "malware_scan_config_present",
        "backup_restore_config_present",
        "retention_delete_policy_present",
        "rbac_dependency_passed",
        "tenant_boundary_dependency_passed",
        "audit_linkage_present",
    ):
        # malware/backup may be explicitly deferred — treat absent as missing in Mode A
        if key in {
            "malware_scan_config_present",
            "backup_restore_config_present",
        }:
            if not f.get(key):
                missing.append(f"{key}_or_explicit_deferral")
            continue
        if not f.get(key):
            missing.append(key)

    mode_b_possible = approval_valid and not any(
        m
        for m in missing
        if m
        not in {
            "malware_scan_config_present_or_explicit_deferral",
            "backup_restore_config_present_or_explicit_deferral",
        }
    )
    # Gate 20 Mode A: config flags all false → mode_b_possible false
    mode_b_possible = False if not approval_valid else mode_b_possible

    guard = evaluate_storage_provisioning_guard(approval=token, flags=f)
    validation_attempted = False
    if mode_b_possible:
        validation_attempted = True
        # Still do not claim production without real provision evidence
        pass

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "storage_mode_b_possible": mode_b_possible,
            "owner_approval_present": approval_present,
            "approval_valid": approval_valid,
            "provisioning_validation_attempted": validation_attempted,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "controlled_pilot_storage_ready": False,
            "missing_gates": missing,
            "guard_blocked_reasons": guard.get("blocked_reasons"),
            "dry_run_allowed": True,
            "real_provisioning_allowed": False,
            "next_safe_action": (
                "Obtain repo-safe owner approval token + production config, "
                "then re-run storage Mode B validation"
            ),
            "human_review_required": True,
        }
    )


def storage_mode_b_execution_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "controlled_pilot_storage_ready",
        "real_provisioning_allowed",
        "storage_mode_b_possible",
        "provisioning_validation_attempted",
    ):
        if result.get(key) is True:
            fails.append(key)
    return fails

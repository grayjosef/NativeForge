"""Storage provisioning execution guard (Block 44)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.storage_feature_flag_service import (
    build_storage_feature_flag_contract,
)
from nativeforge.services.storage_owner_approval_token_service import (
    build_storage_owner_approval_token,
)

SCHEMA_VERSION = "nf_storage_provisioning_execution_guard_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def evaluate_storage_provisioning_guard(
    *,
    approval: dict[str, Any] | None = None,
    flags: dict[str, Any] | None = None,
    full_sca_passed: bool = True,
    pen_test_passed: bool = False,
    login_live: bool = False,
    customer_data_policy_passed: bool = False,
) -> dict[str, Any]:
    token = approval or build_storage_owner_approval_token(present=False)
    f = flags or build_storage_feature_flag_contract()
    blocked: list[str] = []

    dry_run_allowed = True
    real_provisioning_allowed = False

    if not token.get("approval_present"):
        blocked.append("owner_approval_absent")
    if token.get("revoked"):
        blocked.append("approval_revoked")
    if token.get("stale"):
        blocked.append("approval_stale")
    if not token.get("production_storage_approved"):
        blocked.append("production_storage_not_approved")
    if not f.get("production_storage_config_present"):
        blocked.append("production_storage_config_missing")
    for key in (
        "metadata_db_config_present",
        "object_storage_config_present",
        "signed_url_config_present",
        "malware_scan_config_present",
        "backup_restore_config_present",
        "retention_delete_policy_present",
    ):
        if not f.get(key):
            blocked.append(key)
    if not f.get("rbac_dependency_passed"):
        blocked.append("rbac_dependency")
    if not f.get("tenant_boundary_dependency_passed"):
        blocked.append("tenant_boundary")
    if not f.get("audit_linkage_present"):
        blocked.append("audit_linkage")
    if not full_sca_passed:
        blocked.append("full_sca_not_passed")

    # Real provisioning only if approval + configs + not revoked/stale
    if (
        token.get("approval_present")
        and token.get("production_storage_approved")
        and not token.get("revoked")
        and not token.get("stale")
        and f.get("production_storage_enabled")
        and f.get("production_storage_config_present")
    ):
        # Still Gate 19 Mode A: keep real provisioning false without actual config
        real_provisioning_allowed = False
        blocked.append("mode_a_no_live_provisioning")

    customer_persistence_claimed = False
    production_storage_claimed = False
    if (
        real_provisioning_allowed
        and login_live
        and customer_data_policy_passed
        and token.get("customer_persistence_approved")
        and pen_test_passed
    ):
        customer_persistence_claimed = False  # still require explicit validation step

    next_action = (
        "Dry-run provisioning review is allowed; obtain explicit owner approval token "
        "and config before any real provisioning"
        if not token.get("approval_present")
        else "Approval modeled — still validate config and keep production claims false until validated"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "approval_id": token.get("storage_owner_approval_id"),
            "provisioning_allowed": real_provisioning_allowed,
            "dry_run_only": True,
            "dry_run_allowed": dry_run_allowed,
            "real_provisioning_allowed": real_provisioning_allowed,
            "blocked_reasons": blocked,
            "production_storage_claimed": production_storage_claimed,
            "customer_data_persistence_claimed": customer_persistence_claimed,
            "pen_test_passed": pen_test_passed,
            "full_sca_passed": full_sca_passed,
            "next_safe_action": next_action,
            "human_review_required": True,
        }
    )


def storage_provisioning_guard_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "real_provisioning_allowed",
        "provisioning_allowed",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("dry_run_allowed") is not True:
        fails.append("dry_run_not_allowed")
    return fails

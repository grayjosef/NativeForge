"""Storage feature flag contract (Block 42)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_storage_feature_flag_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_storage_feature_flag_id(scope: str = "default") -> str:
    raw = f"sff::{scope}".encode()
    return f"sff_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_storage_feature_flag_contract(
    *,
    environment_scope: str = "local_dev",
    local_dev_storage_enabled: bool = True,
    production_storage_enabled: bool = False,
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "storage_feature_flag_id": make_storage_feature_flag_id(environment_scope),
            "environment_scope": environment_scope,
            "local_dev_storage_enabled": bool(local_dev_storage_enabled),
            "production_storage_enabled": bool(production_storage_enabled),
            "production_storage_config_present": False,
            "owner_approval_present": False,
            "metadata_db_config_present": False,
            "object_storage_config_present": False,
            "malware_scan_config_present": False,
            "signed_url_config_present": False,
            "backup_restore_config_present": False,
            "retention_delete_policy_present": False,
            "audit_linkage_present": True,
            "rbac_dependency_passed": True,  # fixture RBAC
            "tenant_boundary_dependency_passed": True,
            "customer_data_policy_passed": False,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "human_review_required": True,
        }
    )


def storage_feature_flag_invariant_failures(flag: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_enabled",
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "owner_approval_present",
        "production_storage_config_present",
    ):
        if flag.get(key) is True:
            fails.append(key)
    if flag.get("production_storage_enabled") and not flag.get(
        "owner_approval_present"
    ):
        fails.append("prod_enabled_without_approval")
    return fails

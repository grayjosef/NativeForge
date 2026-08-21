"""Production storage readiness validator (Block 42)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.storage_adapter_interface_service import (
    build_storage_adapter_bundle,
)
from nativeforge.services.storage_feature_flag_service import (
    build_storage_feature_flag_contract,
)

SCHEMA_VERSION = "nf_production_storage_readiness_validator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def validate_production_storage_readiness(
    *,
    flags: dict[str, Any] | None = None,
    pen_test_passed: bool = False,
    full_sca_passed: bool = True,
    login_live: bool = False,
) -> dict[str, Any]:
    f = flags or build_storage_feature_flag_contract()
    adapters = build_storage_adapter_bundle(flags=f)
    missing: list[str] = []
    for key in (
        "owner_approval_present",
        "production_storage_config_present",
        "metadata_db_config_present",
        "object_storage_config_present",
        "malware_scan_config_present",
        "signed_url_config_present",
        "backup_restore_config_present",
        "retention_delete_policy_present",
        "customer_data_policy_passed",
    ):
        if not f.get(key):
            missing.append(key)
    if not f.get("rbac_dependency_passed"):
        missing.append("rbac_dependency")
    if not f.get("tenant_boundary_dependency_passed"):
        missing.append("tenant_boundary")
    if not f.get("audit_linkage_present"):
        missing.append("audit_linkage")
    if not pen_test_passed:
        missing.append("pen_test_not_passed")
    if not full_sca_passed:
        missing.append("full_sca_not_passed")
    if not login_live:
        missing.append("login_not_live")

    production_storage_ready = len(missing) == 0 and f.get("production_storage_enabled")
    customer_persistence_ready = bool(
        production_storage_ready and login_live and f.get("customer_data_policy_passed")
    )
    controlled_pilot_storage_ready = bool(
        customer_persistence_ready and pen_test_passed
    )

    # Gate 18: keep claims false
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "production_storage_ready": False,
            "customer_data_persistence_ready": False,
            "controlled_pilot_storage_ready": False,
            "modeled_production_storage_ready": bool(production_storage_ready),
            "modeled_customer_persistence_ready": bool(customer_persistence_ready),
            "modeled_controlled_pilot_storage_ready": bool(
                controlled_pilot_storage_ready
            ),
            "missing_gates": missing,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "adapters": adapters,
            "next_safe_action": (
                "Owner signs approval packet, provisions config, keeps "
                "production_storage_enabled=false until validated"
            ),
            "human_review_required": True,
        }
    )


def production_storage_readiness_validator_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "production_storage_ready",
        "customer_data_persistence_ready",
        "controlled_pilot_storage_ready",
    ):
        if result.get(key) is True:
            fails.append(key)
    return fails

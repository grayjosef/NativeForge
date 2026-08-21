"""Block 42 assembler: storage feature-flag + readiness validator surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.production_storage_readiness_validator_service import (
    production_storage_readiness_validator_invariant_failures,
    validate_production_storage_readiness,
)
from nativeforge.services.storage_adapter_interface_service import (
    build_storage_adapter_bundle,
    storage_adapter_bundle_invariant_failures,
)
from nativeforge.services.storage_feature_flag_service import (
    build_storage_feature_flag_contract,
    storage_feature_flag_invariant_failures,
)

SCHEMA_VERSION = "nf_storage_feature_flag_assembler_v1"
DOC = "docs/operations/219_STORAGE_FEATURE_FLAG_SCAFFOLDING.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_storage_feature_flag_demo_surface() -> dict[str, Any]:
    flags = build_storage_feature_flag_contract()
    adapters = build_storage_adapter_bundle(flags=flags)
    validator = validate_production_storage_readiness(
        flags=flags, pen_test_passed=False, full_sca_passed=True, login_live=False
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 42,
            "title": "Storage feature-flag scaffolding + production readiness validator",
            "docs": [DOC],
            "feature_flags": flags,
            "local_dev_storage_enabled": True,
            "production_storage_enabled": False,
            "owner_approval_present": False,
            "metadata_db_config_present": False,
            "object_storage_config_present": False,
            "malware_scan_config_present": False,
            "signed_url_config_present": False,
            "adapters": adapters,
            "production_adapter_status": (adapters.get("production") or {}).get(
                "status"
            ),
            "validator": validator,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "controlled_pilot_storage_ready": False,
            "missing_gates": validator.get("missing_gates"),
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "buyer_summary": [
                "Local/dev storage remains enabled and validated",
                "Production storage feature flag stays OFF without approval/config",
                "Production adapter stub returns blocked when not configured",
                "Readiness validator keeps production/customer persistence claims false",
            ],
            "next_safe_actions": [
                validator.get("next_safe_action"),
                "Do not enable production_storage_enabled until owner approval + validation",
            ],
            "human_review_required": True,
            "login_live_claimed": False,
        }
    )


def storage_feature_flag_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_enabled",
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "controlled_pilot_storage_ready",
        "login_live_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    fails.extend(
        storage_feature_flag_invariant_failures(surface.get("feature_flags") or {})
    )
    fails.extend(
        storage_adapter_bundle_invariant_failures(surface.get("adapters") or {})
    )
    fails.extend(
        production_storage_readiness_validator_invariant_failures(
            surface.get("validator") or {}
        )
    )
    return fails

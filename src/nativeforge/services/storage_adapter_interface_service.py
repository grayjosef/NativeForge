"""Storage adapter interface and safe stubs (Block 42)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.storage_feature_flag_service import (
    build_storage_feature_flag_contract,
)

SCHEMA_VERSION = "nf_storage_adapter_interface_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def local_dev_storage_adapter() -> dict[str, Any]:
    return {
        "adapter": "local_dev_validated_persistent",
        "status": "available",
        "mutates_production": False,
        "customer_persistence_claimed": False,
    }


def production_storage_adapter_stub(*, flags: dict[str, Any]) -> dict[str, Any]:
    allowed = bool(
        flags.get("production_storage_enabled")
        and flags.get("owner_approval_present")
        and flags.get("production_storage_config_present")
    )
    if not allowed:
        return {
            "adapter": "production_stub",
            "status": "blocked",
            "reason": "feature_flag_or_approval_or_config_missing",
            "mutates_production": False,
            "production_storage_claimed": False,
        }
    return {
        "adapter": "production_stub",
        "status": "configured_not_validated",
        "mutates_production": False,
        "production_storage_claimed": False,
    }


def object_storage_adapter_stub(*, flags: dict[str, Any]) -> dict[str, Any]:
    if not flags.get("object_storage_config_present"):
        return {
            "adapter": "object_storage_stub",
            "status": "blocked",
            "reason": "no_config",
        }
    return {"adapter": "object_storage_stub", "status": "configured_not_validated"}


def signed_url_stub(*, flags: dict[str, Any]) -> dict[str, Any]:
    if not flags.get("signed_url_config_present"):
        return {
            "adapter": "signed_url_stub",
            "status": "blocked",
            "reason": "no_config",
        }
    return {"adapter": "signed_url_stub", "status": "configured_not_validated"}


def malware_scan_stub(*, flags: dict[str, Any]) -> dict[str, Any]:
    if not flags.get("malware_scan_config_present"):
        return {
            "adapter": "malware_scan_stub",
            "status": "blocked",
            "reason": "no_config",
        }
    return {"adapter": "malware_scan_stub", "status": "configured_not_validated"}


def metadata_db_binding_stub(*, flags: dict[str, Any]) -> dict[str, Any]:
    if not flags.get("metadata_db_config_present"):
        return {
            "adapter": "metadata_db_stub",
            "status": "blocked",
            "reason": "no_config",
        }
    return {"adapter": "metadata_db_stub", "status": "configured_not_validated"}


def build_storage_adapter_bundle(
    *, flags: dict[str, Any] | None = None
) -> dict[str, Any]:
    f = flags or build_storage_feature_flag_contract()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "local_dev": local_dev_storage_adapter(),
            "production": production_storage_adapter_stub(flags=f),
            "object_storage": object_storage_adapter_stub(flags=f),
            "signed_url": signed_url_stub(flags=f),
            "malware_scan": malware_scan_stub(flags=f),
            "metadata_db": metadata_db_binding_stub(flags=f),
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "no_production_customer_data_mutation": True,
        }
    )


def storage_adapter_bundle_invariant_failures(bundle: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_data_persistence_claimed",
    ):
        if bundle.get(key) is True:
            fails.append(key)
    prod = bundle.get("production") or {}
    if prod.get("status") not in {"blocked", "configured_not_validated"}:
        fails.append("unexpected_prod_status")
    if prod.get("mutates_production") is True:
        fails.append("mutates_production")
    return fails

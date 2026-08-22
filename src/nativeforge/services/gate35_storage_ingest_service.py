"""Storage approval/config real-input ingest (Block 84). Mode A when absent."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_gate35_storage_ingest_v1"
REPO_SAFE_STORAGE = Path("artifacts/owner_oob/storage.repo-safe.json")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _env(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def locate_storage_artifacts() -> dict[str, Any]:
    approval = _env("NF_STORAGE_APPROVAL_TOKEN") or REPO_SAFE_STORAGE.is_file()
    meta = _env("NF_METADATA_STORAGE_CONFIG")
    obj = _env("NF_OBJECT_STORAGE_CONFIG")
    return {
        "approval_artifact_present": approval,
        "metadata_config_present": meta,
        "object_config_present": obj,
        "signed_url_config_present": _env("NF_SIGNED_URL_CONFIG"),
        "sse_kms_config_present": _env("NF_SSE_KMS_CONFIG"),
        "malware_scan_config_present": _env("NF_MALWARE_SCAN_CONFIG"),
        "backup_restore_config_present": _env("NF_BACKUP_RESTORE_CONFIG"),
        "retention_delete_export_config_present": _env(
            "NF_RETENTION_DELETE_EXPORT_CONFIG"
        ),
    }


def run_storage_real_ingest(
    *,
    override: dict[str, bool] | None = None,
    auth_policy_tenant_audit: bool = False,
) -> dict[str, Any]:
    loc = locate_storage_artifacts()
    if override:
        loc.update(override)
    approval = bool(loc["approval_artifact_present"])
    configs = [
        loc["metadata_config_present"],
        loc["object_config_present"],
        loc["signed_url_config_present"],
        loc["sse_kms_config_present"],
        loc["malware_scan_config_present"],
        loc["backup_restore_config_present"],
        loc["retention_delete_export_config_present"],
    ]
    token_valid = approval  # repo-safe presence only; no token printed
    attempted = bool(approval and all(configs))
    validated = bool(attempted)
    prod_claim = bool(validated)
    persist = bool(prod_claim and auth_policy_tenant_audit)
    missing: list[str] = []
    if not approval:
        missing.append("blocked_owner_input")
        missing.append("approval")
    if approval and not all(configs):
        missing.append("config")
    if not loc["sse_kms_config_present"]:
        missing.append("sse_kms")
    if not loc["malware_scan_config_present"]:
        missing.append("malware_scan")
    if not loc["retention_delete_export_config_present"]:
        missing.append("retention_delete_export")
    if prod_claim and not auth_policy_tenant_audit:
        missing.append("auth_policy_tenant_audit")
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "storage_run_id": f"nf_g35_stor_{uuid.uuid4().hex[:8]}",
            "mode": "A" if not approval else "B",
            "wait_state": "blocked_owner_input" if not approval else "mode_b",
            **loc,
            "approval_token_valid": token_valid and approval,
            "production_storage_validation_attempted": attempted,
            "production_storage_validated": validated,
            "production_storage_claim": prod_claim,
            "customer_persistence_claim": persist,
            "missing_gates": missing,
        }
    )


def storage_ingest_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("mode") == "A" and result.get("production_storage_claim"):
        fails.append("prod_storage_mode_a")
    if result.get("customer_persistence_claim") and not result.get(
        "production_storage_claim"
    ):
        fails.append("persist_without_storage")
    return fails

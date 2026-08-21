"""Storage provisioning dry-run contract (Block 40)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_storage_provisioning_dry_run_v1"
DOC = "docs/operations/213_PRODUCTION_STORAGE_PROVISIONING_DRY_RUN.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_plan_id(label: str = "v1") -> str:
    raw = f"spp::{label}".encode()
    return f"spp_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_storage_provisioning_dry_run_contract(
    *,
    owner_approval_status: str = "pending_owner",
) -> dict[str, Any]:
    dry_run_status = (
        "ready_for_owner_review"
        if owner_approval_status == "pending_owner"
        else "blocked"
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "storage_provisioning_plan_id": make_plan_id(),
            "artifact": DOC,
            "recommended_backend": (
                "managed Postgres + S3-compatible SSE + signed URLs + malware scan"
            ),
            "metadata_database_status": "planned_not_provisioned",
            "object_storage_status": "planned_not_provisioned",
            "signed_url_status": "planned_not_implemented",
            "malware_scan_status": "dependency_required_not_wired",
            "encryption_status": "required_at_rest_planned",
            "backup_restore_status": "planned_not_validated",
            "retention_delete_status": "model_exists_not_production_validated",
            "audit_linkage_status": "contract_ready",
            "rbac_dependency_status": "fixture_enforced_login_not_live",
            "tenant_boundary_dependency_status": "model_enforced",
            "owner_approval_status": owner_approval_status,
            "dry_run_status": dry_run_status,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "production_storage_validated": False,
            "human_review_required": True,
        }
    )


def storage_provisioning_dry_run_invariant_failures(plan: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "production_storage_validated",
    ):
        if plan.get(key) is True:
            fails.append(key)
    if plan.get("owner_approval_status") == "approved" and plan.get(
        "production_storage_claimed"
    ):
        fails.append("claimed_on_approval_only")
    return fails

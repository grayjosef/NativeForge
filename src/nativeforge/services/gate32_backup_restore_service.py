"""Rollback / backup / restore proof, non-prod (Block 73)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_gate32_backup_restore_v1"

STATUSES = (
    "not_started",
    "planned",
    "non_prod_ready",
    "non_prod_rehearsed",
    "validated_non_prod",
    "blocked_missing_storage",
    "blocked_missing_approval",
    "blocked_missing_config",
    "production_not_supported",
    "production_ready_for_review",
    "unknown",
)

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_backup_restore(
    *,
    production_storage: bool = False,
    storage_approval: bool = False,
    storage_config: bool = False,
    non_prod_rehearsed: bool = False,
    restore_evidence_ref: str | None = None,
) -> dict[str, Any]:
    missing: list[str] = []
    backup_status = "planned"
    restore_status = "planned"
    if not production_storage:
        backup_status = "blocked_missing_storage"
        missing.append("production_storage")
    if not storage_approval:
        missing.append("storage_approval")
    if not storage_config:
        missing.append("storage_config")
    if non_prod_rehearsed:
        restore_status = "non_prod_rehearsed"
        if restore_evidence_ref:
            restore_status = "validated_non_prod"
        else:
            missing.append("restore_evidence_ref")
            restore_status = "planned"
    if not restore_evidence_ref:
        if "restore_evidence_ref" not in missing:
            missing.append("restore_evidence_ref")
    prod_backup = bool(production_storage and storage_approval and storage_config)
    prod_restore = False
    _AUDIT.append({"event": "restore_rehearsal", "non_prod": non_prod_rehearsed})
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "rollback_contract": True,
            "backup_contract": True,
            "restore_proof_contract": True,
            "statuses": list(STATUSES),
            "non_prod_backup_manifest": True,
            "non_prod_restore_rehearsal": bool(
                non_prod_rehearsed and restore_evidence_ref
            ),
            "backup_status": backup_status,
            "restore_status": restore_status,
            "rollback_plan_exists": True,
            "production_rollback_claimed": False,
            "production_backup_claimed": prod_backup,
            "production_restore_claimed": prod_restore,
            "customer_persistence_claimed": False,
            "rpo_rto_targets": {"rpo": "unvalidated", "rto": "unvalidated"},
            "audit_events": True,
            "audit_refs": [a["event"] for a in _AUDIT[-3:]],
            "missing_gates": missing,
        }
    )


def backup_restore_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("production_restore_claimed") is True:
        fails.append("prod_restore")
    if result.get("customer_persistence_claimed") is True:
        fails.append("persistence")
    if result.get("production_rollback_claimed") is True:
        fails.append("prod_rollback")
    return fails

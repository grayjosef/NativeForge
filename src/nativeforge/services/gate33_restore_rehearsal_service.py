"""Non-prod restore rehearsal with evidence (Block 77)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_gate33_restore_rehearsal_v1"
_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_restore_rehearsal(
    *,
    production_storage: bool = False,
    restore_attempted: bool = True,
    restore_evidence_ref: str | None = "nf://gate33/non-prod-restore-rehearsal",
    backup_manifest_evidence_ref: str | None = "nf://gate33/non-prod-backup-manifest",
    write_artifact: Path | None = None,
) -> dict[str, Any]:
    run_id = f"nf_restore_{uuid.uuid4().hex[:10]}"
    missing: list[str] = []
    if not restore_evidence_ref:
        missing.append("restore_evidence_ref")
    if not production_storage:
        missing.append("production_storage")
    restore_completed = bool(
        restore_attempted and restore_evidence_ref and not production_storage
    )
    restore_proof = bool(restore_completed and restore_evidence_ref)
    if write_artifact and restore_proof:
        write_artifact.parent.mkdir(parents=True, exist_ok=True)
        write_artifact.write_text(
            json.dumps({"run_id": run_id, "scope": "non_prod"}, indent=2) + "\n",
            encoding="utf-8",
        )
    _AUDIT.append({"event": "restore_rehearsal", "run_id": run_id})
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "restore_rehearsal_contract": True,
            "restore_run_id": run_id,
            "environment_scope": "non_prod",
            "backup_manifest_present": True,
            "backup_manifest_evidence_ref": backup_manifest_evidence_ref,
            "restore_attempted": restore_attempted,
            "restore_completed": restore_completed and bool(restore_evidence_ref),
            "restore_evidence_ref": restore_evidence_ref,
            "restore_proof": restore_proof,
            "rpo_target": "not_production",
            "rto_target": "not_production",
            "rpo_result": "unmeasured_non_prod_model",
            "rto_result": "unmeasured_non_prod_model",
            "restore_steps": [
                "load_non_prod_manifest",
                "validate_evidence_ref",
                "no_op_rollback",
                "record_audit",
            ],
            "rollback_noop": True,
            "production_backup_claimed": False,
            "production_restore_claimed": False,
            "customer_persistence_claimed": False,
            "missing_gates": missing,
            "audit_refs": [a["event"] for a in _AUDIT[-5:]],
        }
    )


def restore_rehearsal_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_backup_claimed",
        "production_restore_claimed",
        "customer_persistence_claimed",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("restore_proof") and not result.get("restore_evidence_ref"):
        fails.append("proof_without_evidence")
    return fails


def clear_restore_audit_for_tests() -> None:
    _AUDIT.clear()

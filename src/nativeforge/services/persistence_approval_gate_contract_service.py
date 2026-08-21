"""Persistent evidence storage approval gate (Campaign Block 23).

OWNER_APPROVED_MIGRATIONS=false by default for this gate.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_persistence_approval_gate_contract_v1"

# Explicit gate constant — do not flip without owner instruction
OWNER_APPROVED_MIGRATIONS = False

APPROVAL_STATUSES = frozenset(
    {
        "not_requested",
        "requested",
        "approved",
        "denied",
        "blocked",
        "not_supported",
    }
)

DRY_RUN_STATUSES = frozenset(
    {
        "not_run",
        "dry_run_ok",
        "dry_run_failed",
        "blocked_pending_approval",
        "not_supported",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_persistence_approval_gate_id(label: str) -> str:
    raw = f"pag::{label}".encode()
    return f"pag_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_persistence_approval_gate_contract(
    *,
    owner_approved_migrations: bool = OWNER_APPROVED_MIGRATIONS,
    owner_approval_status: str | None = None,
) -> dict[str, Any]:
    if owner_approved_migrations:
        # Still require explicit status; this gate run defaults false
        status = (
            owner_approval_status
            if owner_approval_status in APPROVAL_STATUSES
            else "approved"
        )
    else:
        status = "requested"  # approval-ready request prepared, not granted
        if (
            owner_approval_status in APPROVAL_STATUSES
            and owner_approval_status != "approved"
        ):
            status = owner_approval_status

    # Hard: never claim validated persistent without true approval + this flag
    approved = bool(owner_approved_migrations) and status == "approved"
    dry_run = "blocked_pending_approval" if not approved else "dry_run_ok"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "persistence_approval_gate_id": make_persistence_approval_gate_id(
                "evidence_upload_v1"
            ),
            "evidence_intake_contract_reference": "nf_evidence_intake_contract_v1",
            "storage_proposal_reference": (
                "docs/operations/161_EVIDENCE_UPLOAD_STORAGE_PROPOSAL.md"
            ),
            "approval_ready_artifact_reference": (
                "docs/operations/166_PERSISTENT_STORAGE_APPROVAL_GATE.md"
            ),
            "owner_approval_required": True,
            "owner_approval_status": status
            if status in APPROVAL_STATUSES
            else "blocked",
            "owner_approved_migrations_flag": bool(owner_approved_migrations),
            "migration_required": True,
            "migration_applied": False,
            "validated_persistent_adapter_claimed": False,
            "upload_persistence_claimed": False,
            "customer_data_persistence_claimed": False,
            "production_storage_claimed": False,
            "dry_run_status": dry_run if dry_run in DRY_RUN_STATUSES else "not_run",
            "blocker_reasons": [
                "OWNER_APPROVED_MIGRATIONS=false",
                "Alembic migration not applied",
                "validated_persistent adapter unavailable until approval",
                "malware scanning / retention / IAM not production-validated",
            ]
            if not approved
            else [],
            "approval_request_text": (
                "Mayhem: please approve Alembic migration + object-storage path for "
                "nf_evidence_intake_records before any validated_persistent adapter or "
                "upload_persistence claim. Dry-run and rollback plan are documented in "
                "docs/operations/166_PERSISTENT_STORAGE_APPROVAL_GATE.md."
            ),
            "next_safe_action": (
                "Keep fixture/local adapters; do not apply migrations; wait for owner approval"
                if not approved
                else "Run approved dry-run then apply migration under review"
            ),
            "what_would_change_after_approval": [
                "Alembic migration for evidence intake metadata tables",
                "Object-storage or approved local_dev blob path",
                "Possible validated_persistent adapter after validation tests",
            ],
            "submission_ready_claimed": False,
            "final_export_claimed": False,
            "live_ingest_claimed": False,
        }
    )


def persistence_approval_gate_invariant_failures(gate: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "migration_applied",
        "validated_persistent_adapter_claimed",
        "upload_persistence_claimed",
        "customer_data_persistence_claimed",
        "production_storage_claimed",
        "submission_ready_claimed",
        "final_export_claimed",
        "live_ingest_claimed",
    ):
        if gate.get(key) is True:
            fails.append(key)
    if gate.get("owner_approval_required") is not True:
        fails.append("owner_approval_not_required")
    if gate.get("owner_approval_status") not in APPROVAL_STATUSES:
        fails.append("bad_approval_status")
    if gate.get("dry_run_status") not in DRY_RUN_STATUSES:
        fails.append("bad_dry_run_status")
    # Without approved migrations flag, never allow approved+persistent claims
    if not gate.get("owner_approved_migrations_flag"):
        if gate.get("owner_approval_status") == "approved":
            fails.append("approved_without_migrations_flag")
        if gate.get("dry_run_status") not in {
            "blocked_pending_approval",
            "not_run",
            "not_supported",
        }:
            fails.append("dry_run_not_blocked_without_approval")
    return fails

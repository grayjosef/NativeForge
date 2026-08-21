"""Persistent evidence storage approval gate (Campaign Blocks 23/25).

Gate 10: OWNER_APPROVED_MIGRATIONS=true for local_dev_only only.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.persistence_approval_resolver_service import (
    APPROVED_ENVIRONMENT,
    OWNER_APPROVED_MIGRATIONS,
    resolve_persistence_approval_lane,
)

SCHEMA_VERSION = "nf_persistence_approval_gate_contract_v1"

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
        "applied_local_dev",
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
    migration_applied: bool = False,
    validated_local_dev: bool = False,
) -> dict[str, Any]:
    lane = resolve_persistence_approval_lane(
        owner_approved_migrations=owner_approved_migrations,
        approved_environment=APPROVED_ENVIRONMENT
        if owner_approved_migrations
        else "not_approved",
    )
    approved = bool(lane.get("gate10_local_dev_lane"))
    if owner_approval_status in APPROVAL_STATUSES and not approved:
        status = owner_approval_status
    elif approved:
        status = "approved"
    else:
        status = "requested"

    if approved and migration_applied and validated_local_dev:
        dry_run = "applied_local_dev"
    elif approved:
        dry_run = "dry_run_ok"
    else:
        dry_run = "blocked_pending_approval"

    # Local/dev scoped claims only when applied+validated
    local_claims = bool(approved and migration_applied and validated_local_dev)

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
            "applied_artifact_reference": (
                "docs/operations/172_LOCAL_DEV_PERSISTENT_STORAGE_APPLIED.md"
            ),
            "owner_approval_required": True,
            "owner_approval_status": status if status in APPROVAL_STATUSES else "blocked",
            "owner_approved_migrations_flag": bool(owner_approved_migrations),
            "approval_source": lane.get("approval_source"),
            "approval_scope": lane.get("approval_scope"),
            "approved_environment": lane.get("approved_environment"),
            "migration_required": True,
            "migration_allowed": bool(lane.get("migration_allowed")),
            "migration_applied": bool(migration_applied and approved),
            "migration_environment": "local_dev_only"
            if migration_applied and approved
            else None,
            "validated_persistent_adapter_claimed": bool(local_claims),
            "validated_persistent_scope": "local_dev_only" if local_claims else None,
            "upload_persistence_claimed": bool(local_claims),
            "upload_persistence_scope": "local_dev_only" if local_claims else None,
            "customer_data_persistence_claimed": False,
            "production_storage_claimed": False,
            "dry_run_status": dry_run if dry_run in DRY_RUN_STATUSES else "not_run",
            "blocker_reasons": []
            if local_claims
            else (
                [
                    "Await local/dev migration apply + adapter validation"
                    if approved
                    else "OWNER_APPROVED_MIGRATIONS=false",
                    "malware scanning / retention / IAM not production-validated",
                    "production storage not approved",
                ]
            ),
            "approval_request_text": (
                "Gate 10 Mayhem approval: local_dev_only migrations + validated_persistent."
            ),
            "next_safe_action": (
                "Use local/dev validated_persistent; keep production/customer claims false"
                if local_claims
                else (
                    "Run dry-run then apply Alembic 0022 in local/dev"
                    if approved
                    else "Wait for owner approval"
                )
            ),
            "what_remains_blocked_for_production": [
                "Production object storage + IAM",
                "Customer data persistence path",
                "External customer login / multi-tenant auth",
                "Pen-test / SCA pass (not claimed)",
                "Controlled customer pilot GO",
            ],
            "submission_ready_claimed": False,
            "final_export_claimed": False,
            "live_ingest_claimed": False,
        }
    )


def persistence_approval_gate_invariant_failures(gate: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
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
    # Local/dev claims must be scoped
    if gate.get("validated_persistent_adapter_claimed") is True:
        if gate.get("validated_persistent_scope") != "local_dev_only":
            fails.append("validated_persistent_not_local_dev_scoped")
        if gate.get("migration_environment") != "local_dev_only":
            fails.append("migration_env_not_local_dev")
    if gate.get("upload_persistence_claimed") is True:
        if gate.get("upload_persistence_scope") != "local_dev_only":
            fails.append("upload_persistence_not_local_dev_scoped")
    if not gate.get("owner_approved_migrations_flag"):
        if gate.get("owner_approval_status") == "approved":
            fails.append("approved_without_migrations_flag")
        if gate.get("migration_applied") is True:
            fails.append("migration_applied_without_approval")
        if gate.get("validated_persistent_adapter_claimed") is True:
            fails.append("validated_without_approval")
    return fails

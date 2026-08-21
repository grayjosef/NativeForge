"""Production storage owner approval packet (Block 38)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_production_storage_owner_approval_packet_v1"
DOC_ARTIFACT = "docs/operations/206_PRODUCTION_STORAGE_OWNER_APPROVAL_PACKET.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_production_storage_owner_approval_packet() -> dict[str, Any]:
    decisions = [
        {
            "decision_id": "approve_metadata_schema",
            "question": "Approve production metadata schema?",
            "status": "pending_owner",
        },
        {
            "decision_id": "approve_object_storage_backend",
            "question": "Approve object storage backend?",
            "status": "pending_owner",
        },
        {
            "decision_id": "approve_malware_scanning",
            "question": "Approve malware scanning dependency?",
            "status": "pending_owner",
        },
        {
            "decision_id": "approve_retention_delete_baseline",
            "question": "Approve retention/delete policy baseline?",
            "status": "pending_owner",
        },
        {
            "decision_id": "approve_backup_restore",
            "question": "Approve backup/restore approach?",
            "status": "pending_owner",
        },
        {
            "decision_id": "approve_staged_pilot_storage",
            "question": "Approve staged customer pilot storage?",
            "status": "pending_owner",
        },
        {
            "decision_id": "approve_implementation_scope",
            "question": "Approve implementation scope?",
            "status": "pending_owner",
        },
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact": DOC_ARTIFACT,
            "decisions_requested": decisions,
            "all_decisions_pending": True,
            "owner_approval_granted": False,
            "production_storage_approved": False,
            "production_storage_validated": False,
            "customer_data_persistence_claimed": False,
            "apply_production_storage_changes": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "note": ("Do not apply production storage changes without owner approval"),
            "human_review_required": True,
        }
    )


def production_storage_owner_approval_invariant_failures(
    packet: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "owner_approval_granted",
        "production_storage_approved",
        "production_storage_validated",
        "customer_data_persistence_claimed",
        "apply_production_storage_changes",
    ):
        if packet.get(key) is True:
            fails.append(key)
    if packet.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    return fails

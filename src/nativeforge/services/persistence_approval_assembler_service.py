"""Assemble persistence approval + local/dev storage demo surface (Blocks 23/25)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.evidence_storage_adapter_service import (
    run_storage_adapter_dry_run,
    storage_adapter_dry_run_invariant_failures,
)
from nativeforge.services.persistence_approval_gate_contract_service import (
    OWNER_APPROVED_MIGRATIONS,
    build_persistence_approval_gate_contract,
    persistence_approval_gate_invariant_failures,
)
from nativeforge.services.persistence_approval_resolver_service import (
    resolve_persistence_approval_lane,
)
from nativeforge.services.validated_persistent_evidence_adapter_service import (
    run_validated_persistent_lifecycle_smoke,
)

SCHEMA_VERSION = "nf_persistence_approval_assembler_v1"
_DEMO_LIFECYCLE_DB = Path("artifacts/local_dev_evidence_demo.sqlite3")

# Set true after migration apply + lifecycle smoke in this gate
LOCAL_DEV_MIGRATION_APPLIED = True
LOCAL_DEV_VALIDATED = True


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_persistence_approval_demo_surface() -> dict[str, Any]:
    lane = resolve_persistence_approval_lane()
    gate = build_persistence_approval_gate_contract(
        owner_approved_migrations=OWNER_APPROVED_MIGRATIONS,
        migration_applied=LOCAL_DEV_MIGRATION_APPLIED,
        validated_local_dev=LOCAL_DEV_VALIDATED,
    )
    dry = run_storage_adapter_dry_run(
        owner_approved_migrations=OWNER_APPROVED_MIGRATIONS,
        migration_applied=LOCAL_DEV_MIGRATION_APPLIED,
        validated_local_dev=LOCAL_DEV_VALIDATED,
    )
    lifecycle = run_validated_persistent_lifecycle_smoke(db_path=_DEMO_LIFECYCLE_DB)
    local_ok = bool(
        gate.get("validated_persistent_adapter_claimed")
        and lifecycle.get("overall_status") == "PASS"
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 25,
            "title": "Local/dev persistent evidence storage (Gate 10)",
            "gate": gate,
            "approval_lane": lane,
            "dry_run": dry,
            "lifecycle_smoke": {
                "overall_status": lifecycle.get("overall_status"),
                "fails": lifecycle.get("fails") or [],
                "sample_evidence_intake_id": lifecycle.get("sample_evidence_intake_id"),
            },
            "buyer_summary": [
                "Local/dev Alembic migration applied for nf_evidence_intake_records",
                "validated_persistent adapter works in local/dev only",
                "Upload/evidence persistence validated in local/dev — not production",
                "Customer data persistence and production storage remain false",
                "Controlled customer pilot remains NO_GO; login not live",
            ],
            "owner_approval_status": gate.get("owner_approval_status"),
            "approval_source": gate.get("approval_source"),
            "approval_scope": gate.get("approval_scope"),
            "approved_environment": gate.get("approved_environment"),
            "migration_required": True,
            "migration_applied": bool(gate.get("migration_applied")),
            "migration_environment": gate.get("migration_environment"),
            "validated_persistent_adapter_claimed": bool(local_ok),
            "validated_persistent_scope": "local_dev_only" if local_ok else None,
            "upload_persistence_claimed": bool(local_ok),
            "upload_persistence_scope": "local_dev_only" if local_ok else None,
            "customer_data_persistence_claimed": False,
            "production_storage_claimed": False,
            "login_live_claimed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "dry_run_status": gate.get("dry_run_status"),
            "next_safe_action": gate.get("next_safe_action"),
            "what_remains_blocked_for_production": gate.get(
                "what_remains_blocked_for_production"
            ),
            "storage_adapters": dry.get("available_adapters") or [],
            "live_ingest_claimed": False,
        }
    )


def persistence_approval_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "customer_data_persistence_claimed",
        "production_storage_claimed",
        "login_live_claimed",
        "live_ingest_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "GO":
        fails.append("customer_pilot_go")
    if surface.get("validated_persistent_adapter_claimed") is True:
        if surface.get("validated_persistent_scope") != "local_dev_only":
            fails.append("validated_scope")
        if (surface.get("lifecycle_smoke") or {}).get("overall_status") != "PASS":
            fails.append("lifecycle_not_pass")
    fails.extend(
        persistence_approval_gate_invariant_failures(surface.get("gate") or {})
    )
    fails.extend(
        storage_adapter_dry_run_invariant_failures(surface.get("dry_run") or {})
    )
    return fails

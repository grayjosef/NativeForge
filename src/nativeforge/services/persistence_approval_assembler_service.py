"""Assemble persistence approval gate demo surface (Block 23)."""

from __future__ import annotations

import json
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

SCHEMA_VERSION = "nf_persistence_approval_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_persistence_approval_demo_surface() -> dict[str, Any]:
    gate = build_persistence_approval_gate_contract(
        owner_approved_migrations=OWNER_APPROVED_MIGRATIONS
    )
    dry = run_storage_adapter_dry_run(
        owner_approved_migrations=OWNER_APPROVED_MIGRATIONS
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 23,
            "title": "Persistent evidence storage approval gate",
            "gate": gate,
            "dry_run": dry,
            "buyer_summary": [
                "Evidence storage design is approval-ready; migrations not applied",
                "Fixture/local-dev adapters work; validated_persistent unavailable",
                "Upload / customer / production persistence claims remain false",
                "Owner approval required before any durable storage path",
            ],
            "owner_approval_status": gate.get("owner_approval_status"),
            "migration_required": True,
            "migration_applied": False,
            "validated_persistent_adapter_claimed": False,
            "upload_persistence_claimed": False,
            "customer_data_persistence_claimed": False,
            "production_storage_claimed": False,
            "dry_run_status": gate.get("dry_run_status"),
            "next_safe_action": gate.get("next_safe_action"),
            "approval_request_text": gate.get("approval_request_text"),
            "storage_adapters": dry.get("available_adapters") or [],
            "live_ingest_claimed": False,
        }
    )


def persistence_approval_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "migration_applied",
        "validated_persistent_adapter_claimed",
        "upload_persistence_claimed",
        "customer_data_persistence_claimed",
        "production_storage_claimed",
        "live_ingest_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(
        persistence_approval_gate_invariant_failures(surface.get("gate") or {})
    )
    fails.extend(
        storage_adapter_dry_run_invariant_failures(surface.get("dry_run") or {})
    )
    return fails

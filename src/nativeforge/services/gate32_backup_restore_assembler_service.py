"""Block 73 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate32_backup_restore_service import (
    backup_restore_invariant_failures,
    resolve_backup_restore,
)

SCHEMA_VERSION = "nf_gate32_backup_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_backup_restore_demo_surface() -> dict[str, Any]:
    result = resolve_backup_restore()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 73,
            "title": "Rollback / backup / restore proof (non-prod)",
            "rollback_contract": True,
            "backup_contract": True,
            "restore_proof_contract": True,
            "non_prod_backup_manifest": True,
            "non_prod_restore_rehearsal": False,
            "production_backup_claimed": False,
            "production_restore_claimed": False,
            "customer_persistence_claimed": False,
            "production_rollback_claimed": False,
            "missing_gates": result.get("missing_gates"),
            "next_owner_action": "Production backup remains blocked without storage",
            "buyer_summary": [
                "Rollback plan exists; production restore remains false",
                "Non-prod manifest is not production backup proof",
            ],
            "next_safe_actions": ["Do not claim production restore from non-prod"],
            "result": result,
        }
    )


def backup_restore_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_backup_claimed",
        "production_restore_claimed",
        "customer_persistence_claimed",
        "production_rollback_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(backup_restore_invariant_failures(surface.get("result") or {}))
    return fails

"""Block 77 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate33_restore_rehearsal_service import (
    restore_rehearsal_invariant_failures,
    run_restore_rehearsal,
)

SCHEMA_VERSION = "nf_gate33_restore_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_restore_rehearsal_demo_surface() -> dict[str, Any]:
    result = run_restore_rehearsal()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 77,
            "title": "Non-prod restore rehearsal with evidence",
            "restore_rehearsal_contract": True,
            "backup_manifest_evidence": bool(
                result.get("backup_manifest_evidence_ref")
            ),
            "restore_attempted": result.get("restore_attempted"),
            "restore_completed": result.get("restore_completed"),
            "restore_evidence_ref": result.get("restore_evidence_ref"),
            "production_backup_claimed": False,
            "production_restore_claimed": False,
            "customer_persistence_claimed": False,
            "missing_gates": result.get("missing_gates"),
            "next_owner_action": "Non-prod model is not production restore",
            "buyer_summary": [
                "In-process non-prod rehearsal recorded with evidence ref",
                "Production backup/restore and persistence stay false",
            ],
            "next_safe_actions": ["Do not claim production restore"],
            "result": result,
        }
    )


def restore_rehearsal_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_backup_claimed",
        "production_restore_claimed",
        "customer_persistence_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(restore_rehearsal_invariant_failures(surface.get("result") or {}))
    return fails

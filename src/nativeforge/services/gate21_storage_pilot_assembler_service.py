"""Block 48 assembler: storage approval ingest + pilot resolver surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate21_storage_pilot_rerun_service import (
    gate21_storage_pilot_rerun_invariant_failures,
    run_gate21_storage_pilot_rerun,
)
from nativeforge.services.storage_approval_token_ingest_service import (
    storage_approval_token_ingest_invariant_failures,
)

SCHEMA_VERSION = "nf_gate21_storage_pilot_assembler_v1"
DOCS = [
    "docs/operations/236_GATE21_STORAGE_APPROVAL_INGEST_RESULTS.md",
    "docs/operations/237_GATE21_EXTERNAL_GATE_REPORT.md",
]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_gate21_storage_pilot_demo_surface() -> dict[str, Any]:
    rerun = run_gate21_storage_pilot_rerun()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 48,
            "title": "Storage approval ingest + controlled pilot resolver rerun",
            "docs": DOCS,
            "owner_storage_approval_present": False,
            "approval_valid": False,
            "provisioning_validation_attempted": False,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "pen_test_evidence_captured": False,
            "pen_test_passed": False,
            "final_controlled_pilot_status": rerun.get("final_controlled_pilot_status"),
            "production_rollout_status": rerun.get("production_rollout_status"),
            "missing_gates": rerun.get("missing_gates"),
            "login_live_claimed": False,
            "buyer_summary": [
                "This Gate 21 prompt alone is not storage approval",
                "No approval token file → production_storage remains false",
                "Approval alone would not validate storage without config/provisioning",
                "Controlled customer pilot remains NO_GO / CONDITIONAL_INTERNAL_ONLY",
            ],
            "next_safe_actions": list(rerun.get("owner_next_actions") or []),
            "human_review_required": True,
            "rerun": rerun,
        }
    )


def gate21_storage_pilot_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "owner_storage_approval_present",
        "approval_valid",
        "provisioning_validation_attempted",
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "pen_test_evidence_captured",
        "pen_test_passed",
        "login_live_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("final_controlled_pilot_status") in {
        "CONTROLLED_CUSTOMER_GO",
        "GO",
    }:
        fails.append("pilot_go")
    fails.extend(
        storage_approval_token_ingest_invariant_failures(
            (surface.get("rerun") or {}).get("ingest") or {}
        )
    )
    fails.extend(
        gate21_storage_pilot_rerun_invariant_failures(surface.get("rerun") or {})
    )
    return fails

"""Assemble operator readiness demo surface (Campaign Block 22)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.operator_readiness_contract_service import (
    build_operator_readiness_contract,
    operator_readiness_invariant_failures,
)

SCHEMA_VERSION = "nf_operator_readiness_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_operator_readiness_demo_surface() -> dict[str, Any]:
    contract = build_operator_readiness_contract()
    matrix = contract.get("go_no_go_matrix") or []
    by_target = {r.get("target"): r for r in matrix}
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 22,
            "title": "Operator enablement / production readiness checklist",
            "contract": contract,
            "buyer_summary": [
                "Operator checklist consolidates smokes, claim boundaries, and blockers",
                "Monday demo can be GO while production/upload/collab remain NO_GO",
                "Pen-test not passed; production not ready; uploads not durable",
                "Commands and fallback path are documented for handover",
            ],
            "monday_demo_status": (by_target.get("monday_demo") or {}).get("status"),
            "internal_pilot_status": (by_target.get("internal_pilot") or {}).get(
                "status"
            ),
            "controlled_customer_pilot_status": (
                by_target.get("controlled_customer_pilot") or {}
            ).get("status"),
            "production_rollout_status": (
                by_target.get("production_rollout") or {}
            ).get("status"),
            "upload_rollout_status": (
                by_target.get("upload_persistence_rollout") or {}
            ).get("status"),
            "collaboration_rollout_status": (
                by_target.get("collaboration_rollout") or {}
            ).get("status"),
            "live_source_rollout_status": (
                by_target.get("live_source_rollout") or {}
            ).get("status"),
            "go_no_go_matrix": matrix,
            "blockers": contract.get("blockers") or [],
            "operator_next_actions": contract.get("operator_next_actions") or [],
            "required_commands": contract.get("required_commands") or [],
            "smoke_commands": contract.get("smoke_commands") or [],
            "production_ready_claimed": False,
            "pen_test_passed_claimed": False,
            "upload_persistence_claimed": False,
            "submission_ready_claimed": False,
            "final_export_claimed": False,
            "collaboration_matching_claimed": False,
            "live_customer_login_claimed": False,
            "live_ingest_claimed": False,
        }
    )


def operator_readiness_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_ready_claimed",
        "pen_test_passed_claimed",
        "upload_persistence_claimed",
        "submission_ready_claimed",
        "final_export_claimed",
        "collaboration_matching_claimed",
        "live_customer_login_claimed",
        "live_ingest_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(operator_readiness_invariant_failures(surface.get("contract") or {}))
    if surface.get("production_rollout_status") == "GO":
        fails.append("production_go")
    if surface.get("upload_rollout_status") == "GO":
        fails.append("upload_go")
    if surface.get("collaboration_rollout_status") == "GO":
        fails.append("collab_go")
    if not surface.get("go_no_go_matrix"):
        fails.append("no_matrix")
    return fails

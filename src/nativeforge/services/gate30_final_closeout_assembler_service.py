"""Block 65 assembler: 3000-sprint closeout surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate30_final_closeout_service import (
    build_3000_sprint_closeout,
    final_closeout_invariant_failures,
)

SCHEMA_VERSION = "nf_gate30_closeout_assembler_v1"
DOCS = [
    "docs/operations/300_NATIVEFORGE_3000_SPRINT_PRODUCTION_GRADE_CLOSEOUT.md",
    "docs/operations/301_GATE30_FINAL_PILOT_GO_NO_GO_PACKET.md",
    "docs/operations/302_GATE30_OWNER_MODEB_EXECUTION_PACKET.md",
    "docs/operations/303_GATE30_FINAL_ALLOWED_FORBIDDEN_CLAIMS.md",
]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_final_closeout_demo_surface() -> dict[str, Any]:
    result = build_3000_sprint_closeout()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 65,
            "title": "3000-sprint production-grade closeout",
            "docs": DOCS,
            "final_pilot_resolver": True,
            "final_production_rollout_resolver": True,
            "final_claim_freeze": True,
            "evidence_map": result.get("evidence_map"),
            "blocker_map": result.get("blocker_map"),
            "owner_action_matrix": result.get("owner_action_matrix"),
            "controlled_customer_pilot_status": result.get(
                "controlled_customer_pilot_status"
            ),
            "production_rollout_status": result.get("production_rollout_status"),
            "allowed_claims": result.get("allowed_claims"),
            "forbidden_claims": result.get("forbidden_claims"),
            "login_live_claimed": False,
            "production_storage_claimed": False,
            "pen_test_passed_claimed": False,
            "mode_b_executed_claimed": False,
            "fake_pilot_ready": False,
            "fake_production_ready": False,
            "next_owner_action": result.get("next_owner_action"),
            "buyer_summary": [
                "3000-sprint campaign closed with a hard GO/NO-GO truth packet",
                "Controlled customer pilot remains CONDITIONAL_INTERNAL_ONLY",
                "Production rollout remains NO_GO",
                "Every allowed claim has evidence; every forbidden claim has a reason",
            ],
            "next_safe_actions": [
                result.get("next_owner_action"),
                "Do not treat closeout as production-ready",
            ],
            "human_review_required": True,
            "result": result,
        }
    )


def final_closeout_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_storage_claimed",
        "pen_test_passed_claimed",
        "mode_b_executed_claimed",
        "fake_pilot_ready",
        "fake_production_ready",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    fails.extend(final_closeout_invariant_failures(surface.get("result") or {}))
    return fails

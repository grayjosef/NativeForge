"""Block 60 assembler: cutover checklist + claim freeze surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate27_cutover_claim_freeze_service import (
    build_claim_freeze_matrix,
    build_production_cutover_checklist,
    cutover_claim_freeze_invariant_failures,
)
from nativeforge.services.gate27_owner_unlock_packet_service import (
    build_owner_unlock_packet,
)

SCHEMA_VERSION = "nf_gate27_cutover_assembler_v1"
DOC = "docs/operations/273_GATE27_PRODUCTION_CUTOVER_CHECKLIST.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_cutover_claim_freeze_demo_surface() -> dict[str, Any]:
    unlock = build_owner_unlock_packet()
    checklist = build_production_cutover_checklist(unlock=unlock)
    freeze = build_claim_freeze_matrix(unlock=unlock, checklist=checklist)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 60,
            "title": "Production cutover checklist + final claim freeze",
            "docs": [DOC, "docs/operations/274_GATE27_FINAL_CLAIM_FREEZE_MATRIX.md"],
            "production_cutover_checklist": True,
            "controlled_pilot_checklist": True,
            "production_rollout_checklist": True,
            "claim_freeze_contract": True,
            "allowed_claims": [
                a["claim"] for a in (freeze.get("allowed_claims") or [])
            ],
            "conditional_claims": [
                c["claim"] for c in (freeze.get("conditional_claims") or [])
            ],
            "forbidden_claims": [
                f["claim"] for f in (freeze.get("forbidden_claims") or [])
            ],
            "owner_next_actions": [
                a["action"] for a in (freeze.get("owner_next_action_matrix") or [])
            ],
            "controlled_customer_pilot_status": freeze.get(
                "controlled_customer_pilot_status"
            ),
            "production_rollout_status": freeze.get("production_rollout_status"),
            "login_live_claimed": False,
            "production_storage_claimed": False,
            "customer_persistence_claimed": False,
            "pen_test_passed_claimed": False,
            "fake_production_ready": False,
            "fake_pilot_ready": False,
            "fake_secure_badge": False,
            "buyer_summary": [
                "Cutover checklist covers auth, storage, security, product, ops, UX",
                "Claim freeze lists allowed/conditional/forbidden with evidence",
                "Controlled pilot stays CONDITIONAL_INTERNAL_ONLY; rollout NO_GO",
                "No fake production-ready, pilot-ready, or secure badges",
            ],
            "next_safe_actions": freeze.get("owner_next_action_matrix")
            and [a["action"] for a in freeze["owner_next_action_matrix"]]
            or [],
            "human_review_required": True,
            "checklist": checklist,
            "freeze": freeze,
        }
    )


def cutover_claim_freeze_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_storage_claimed",
        "customer_persistence_claimed",
        "pen_test_passed_claimed",
        "fake_production_ready",
        "fake_pilot_ready",
        "fake_secure_badge",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    fails.extend(cutover_claim_freeze_invariant_failures(surface.get("freeze") or {}))
    return fails

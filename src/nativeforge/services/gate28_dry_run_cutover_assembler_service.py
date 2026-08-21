"""Block 62 assembler: dry-run cutover surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate28_dry_run_cutover_service import (
    dry_run_cutover_invariant_failures,
    run_production_dry_run_cutover,
)

SCHEMA_VERSION = "nf_gate28_dry_run_cutover_assembler_v1"
DOC = "docs/operations/279_GATE28_PRODUCTION_DRY_RUN_CUTOVER.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_dry_run_cutover_demo_surface() -> dict[str, Any]:
    result = run_production_dry_run_cutover()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 62,
            "title": "Production dry-run cutover + final freeze verification",
            "docs": [DOC, "docs/operations/280_GATE28_FINAL_FREEZE_VERIFICATION.md"],
            "dry_run_cutover_contract": True,
            "first_hard_blocker": result.get("first_hard_blocker"),
            "downstream_step_handling": "skipped_after_blocker",
            "skipped_after_blocker_count": result.get("skipped_after_blocker_count"),
            "sca_evidence_check": result.get("sca_evidence_check"),
            "final_freeze_verified": True,
            "controlled_customer_pilot_status": result.get(
                "controlled_customer_pilot_status"
            ),
            "production_rollout_status": result.get("production_rollout_status"),
            "production_cutover_executed": False,
            "login_live_claimed": False,
            "production_storage_claimed": False,
            "pen_test_passed_claimed": False,
            "fake_cutover_complete": False,
            "fake_pilot_ready": False,
            "owner_next_action": result.get("owner_next_action"),
            "buyer_summary": [
                "Dry-run walks 22 cutover steps and stops at the first hard blocker",
                "Mode A stops at Auth0; downstream steps are skipped_after_blocker",
                "Final claim freeze verified; no production/customer mutation",
                "Controlled pilot stays below GO; rollout stays NO_GO",
            ],
            "next_safe_actions": [
                result.get("owner_next_action"),
                "Do not claim production cutover complete from dry-run",
            ],
            "human_review_required": True,
            "result": result,
        }
    )


def dry_run_cutover_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_cutover_executed",
        "login_live_claimed",
        "production_storage_claimed",
        "pen_test_passed_claimed",
        "fake_cutover_complete",
        "fake_pilot_ready",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    fails.extend(dry_run_cutover_invariant_failures(surface.get("result") or {}))
    return fails

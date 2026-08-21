"""Block 61 assembler: Mode B rehearsal surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate28_mode_b_rehearsal_service import (
    mode_b_rehearsal_invariant_failures,
    run_mode_b_rehearsal,
)

SCHEMA_VERSION = "nf_gate28_mode_b_rehearsal_assembler_v1"
DOC = "docs/operations/278_GATE28_MODEB_EXECUTION_REHEARSAL.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_mode_b_rehearsal_demo_surface() -> dict[str, Any]:
    result = run_mode_b_rehearsal(use_synthetic=True)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 61,
            "title": "Mode B live unlock rehearsal",
            "docs": [DOC],
            "rehearsal_contract": True,
            "mode": result.get("mode"),
            "real_owner_inputs_present": False,
            "synthetic_fixture_used": True,
            "auth0_rehearsed": True,
            "storage_rehearsed": True,
            "pen_test_rehearsed": True,
            "claim_freeze_verified": True,
            "mode_b_executed_claimed": False,
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "production_storage_claimed": False,
            "customer_persistence_claimed": False,
            "pen_test_passed_claimed": False,
            "controlled_customer_pilot_go_claimed": False,
            "missing_real_inputs": result.get("missing_real_inputs"),
            "no_secret_validation": True,
            "fake_mode_b": False,
            "controlled_customer_pilot_status": "CONDITIONAL_INTERNAL_ONLY",
            "production_rollout_status": "PRODUCTION_ROLLOUT_NO_GO",
            "next_owner_action": result.get("next_owner_action"),
            "buyer_summary": [
                "Mode B rehearsal uses synthetic non-secret fixtures only",
                "Synthetic fixtures prove control flow; they do not unlock live claims",
                "Claim freeze verified; Mode B executed remains false",
                "Exact missing real owner inputs remain visible",
            ],
            "next_safe_actions": [
                result.get("next_owner_action"),
                "Do not treat synthetic rehearsal as Mode B executed",
            ],
            "human_review_required": True,
            "result": result,
        }
    )


def mode_b_rehearsal_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "mode_b_executed_claimed",
        "login_live_claimed",
        "production_auth_claimed",
        "production_storage_claimed",
        "customer_persistence_claimed",
        "pen_test_passed_claimed",
        "controlled_customer_pilot_go_claimed",
        "fake_mode_b",
        "real_owner_inputs_present",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(mode_b_rehearsal_invariant_failures(surface.get("result") or {}))
    return fails

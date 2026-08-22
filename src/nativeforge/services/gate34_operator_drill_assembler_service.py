"""Block 81 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate34_operator_drill_service import (
    drill_invariant_failures,
    run_operator_drills,
)

SCHEMA_VERSION = "nf_gate34_drill_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_operator_drill_demo_surface() -> dict[str, Any]:
    result = run_operator_drills()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 81,
            "title": "Operator runbook drill (demo route)",
            "drill_contract": True,
            "drills_passed": result.get("drills_passed"),
            "pilot_go_claimed": False,
            "production_rollout_claimed": False,
            "alert_sent_claimed": False,
            "production_restore_claimed": False,
            "next_owner_action": "Drill pass is not production pass",
            "buyer_summary": [
                "Demo-route drills can pass with evidence refs",
                "Drill pass does not unlock customer pilot or production restore",
            ],
            "next_safe_actions": ["Do not treat drill_passed as production-ready"],
            "result": result,
        }
    )


def operator_drill_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    if surface.get("pilot_go_claimed") is True:
        fails.append("pilot_go")
    fails.extend(drill_invariant_failures(surface.get("result") or {}))
    return fails

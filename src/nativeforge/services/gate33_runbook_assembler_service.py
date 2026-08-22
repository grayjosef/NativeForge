"""Block 78 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate33_runbook_service import (
    resolve_runbooks_and_checklist,
    runbook_invariant_failures,
)

SCHEMA_VERSION = "nf_gate33_runbook_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_runbook_demo_surface() -> dict[str, Any]:
    result = resolve_runbooks_and_checklist()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 78,
            "title": "Operator runbooks + remaining non-owner checklist",
            "runbook_index": True,
            "controlled_pilot_runbook": True,
            "source_probe_runbook": True,
            "healthcheck_runbook": True,
            "restore_runbook": True,
            "incident_triage_runbook": True,
            "owner_gated_blockers": result.get("owner_gated_blockers"),
            "non_owner_items": result.get("non_owner_items"),
            "next_action_sequence": result.get("next_action_sequence"),
            "controlled_customer_pilot_status": result.get(
                "controlled_customer_pilot_status"
            ),
            "production_rollout_status": result.get("production_rollout_status"),
            "allowed_claims": result.get("allowed_claims"),
            "forbidden_claims": result.get("forbidden_claims"),
            "next_owner_action": "Provide OIDC_*, storage approval/config, pen-test report",
            "buyer_summary": [
                "Runbooks exist; owner-gated work stays owner-gated",
                "Completed checklist rows require evidence refs",
            ],
            "next_safe_actions": result.get("next_action_sequence"),
            "result": result,
        }
    )


def runbook_demo_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if surface.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    fails.extend(runbook_invariant_failures(surface.get("result") or {}))
    return fails

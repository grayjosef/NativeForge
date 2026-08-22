"""Block 79 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate34_owner_wait_service import (
    owner_wait_invariant_failures,
    resolve_owner_wait_state,
)

SCHEMA_VERSION = "nf_gate34_wait_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_owner_wait_demo_surface() -> dict[str, Any]:
    result = resolve_owner_wait_state()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 79,
            "title": "Owner-input wait-state",
            "wait_state_contract": True,
            "owner_blockers": result.get("owner_blockers"),
            "external_vendor_blockers": result.get("external_vendor_blockers"),
            "policy_decision_blockers": result.get("policy_decision_blockers"),
            "no_progress_without_input": True,
            "live_claims_unlocked": False,
            "missing_gates": result.get("missing_gates"),
            "next_owner_action": "Provide OIDC_*, storage approval/config, pen-test report",
            "buyer_summary": [
                "Missing owner input is a launch blocker, not backlog",
                "Synthetic fixtures and prompt text cannot satisfy owner input",
            ],
            "next_safe_actions": ["Do not rehearse missing owner inputs as progress"],
            "result": result,
        }
    )


def owner_wait_demo_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if surface.get("live_claims_unlocked") is True:
        fails.append("live_unlocked")
    fails.extend(owner_wait_invariant_failures(surface.get("result") or {}))
    return fails

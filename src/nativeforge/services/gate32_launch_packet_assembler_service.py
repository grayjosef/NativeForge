"""Block 74 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate32_launch_packet_service import (
    build_launch_packet,
    launch_packet_invariant_failures,
)

SCHEMA_VERSION = "nf_gate32_launch_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_launch_packet_demo_surface() -> dict[str, Any]:
    result = build_launch_packet()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 74,
            "title": "Controlled-pilot launch packet",
            "launch_packet_contract": True,
            "launch_status": result.get("launch_status"),
            "non_owner_blockers": result.get("non_owner_blockers"),
            "owner_gated_blockers": result.get("owner_gated_blockers"),
            "external_vendor_blockers": result.get("external_vendor_blockers"),
            "next_action_sequence": result.get("next_action_sequence"),
            "controlled_customer_pilot_status": result.get(
                "controlled_customer_pilot_status"
            ),
            "production_rollout_status": result.get("production_rollout_status"),
            "allowed_claims": result.get("allowed_claims"),
            "forbidden_claims": result.get("forbidden_claims"),
            "next_owner_action": "Provide OIDC_*, storage approval/config, pen-test report",
            "buyer_summary": [
                "Launch packet separates owner vs non-owner blockers",
                "Ready for owner review is not customer pilot GO",
            ],
            "next_safe_actions": result.get("next_action_sequence"),
            "result": result,
        }
    )


def launch_packet_demo_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if surface.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    fails.extend(launch_packet_invariant_failures(surface.get("result") or {}))
    return fails

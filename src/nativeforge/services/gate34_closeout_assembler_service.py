"""Block 82 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate34_closeout_service import (
    build_pre_owner_closeout,
    closeout_invariant_failures,
)

SCHEMA_VERSION = "nf_gate34_closeout_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_closeout_demo_surface() -> dict[str, Any]:
    result = build_pre_owner_closeout(head="c1ffc43+")
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 82,
            "title": "Pre-owner closeout packet",
            "closeout_packet_contract": True,
            "owner_input_package_checklist": result.get(
                "owner_input_package_checklist"
            ),
            "external_vendor_package_checklist": result.get(
                "external_vendor_package_checklist"
            ),
            "post_owner_rerun_sequence": result.get("post_owner_rerun_sequence"),
            "controlled_customer_pilot_status": result.get(
                "controlled_customer_pilot_status"
            ),
            "production_rollout_status": result.get("production_rollout_status"),
            "allowed_claims": result.get("allowed_claims"),
            "forbidden_claims": result.get("forbidden_claims"),
            "next_owner_action": "Deliver OIDC_*, storage approval/config, pen-test package",
            "buyer_summary": [
                "Non-owner work is pushed as far as useful",
                "Customer pilot stays NO_GO until owner and vendor inputs validate",
            ],
            "next_safe_actions": result.get("post_owner_validator_sequence"),
            "result": result,
        }
    )


def closeout_demo_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if surface.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    fails.extend(closeout_invariant_failures(surface.get("result") or {}))
    return fails

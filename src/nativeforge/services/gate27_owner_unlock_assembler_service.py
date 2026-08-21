"""Block 59 assembler: owner Mode B unlock packet surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate27_owner_unlock_packet_service import (
    build_owner_unlock_packet,
    owner_unlock_packet_invariant_failures,
)

SCHEMA_VERSION = "nf_gate27_owner_unlock_assembler_v1"
DOC = "docs/operations/272_GATE27_OWNER_MODEB_UNLOCK_PACKET.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_owner_unlock_demo_surface() -> dict[str, Any]:
    packet = build_owner_unlock_packet()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 59,
            "title": "Owner Mode B unlock packet",
            "docs": [DOC],
            "owner_unlock_packet_contract": True,
            "mode": packet.get("mode"),
            "mode_b_ready": False,
            "mode_b_executed": False,
            "auth0_complete": packet.get("auth0_complete"),
            "storage_complete": packet.get("storage_complete"),
            "security_ready_for_ingest": packet.get("security_ready_for_ingest"),
            "missing_owner_inputs": packet.get("missing_owner_inputs"),
            "repo_safe_artifact_map": packet.get("repo_safe_artifact_map"),
            "out_of_band_config_secret_map": packet.get(
                "out_of_band_config_secret_map"
            ),
            "no_secret_validation": True,
            "login_live_claimed": False,
            "production_storage_claimed": False,
            "pen_test_passed_claimed": False,
            "customer_persistence_claimed": False,
            "controlled_customer_pilot_status": "CONDITIONAL_INTERNAL_ONLY",
            "production_rollout_status": "PRODUCTION_ROLLOUT_NO_GO",
            "prompt_alone_is_not_approval": True,
            "fake_mode_b": False,
            "next_owner_action": packet.get("next_owner_action"),
            "buyer_summary": [
                "Owner unlock packet lists exact Auth0, storage, and pen-test inputs",
                "Repo-safe vs out-of-band secrets are split; secrets never in repo",
                "Mode A until packet complete; Mode B-ready still does not auto-GO",
                "Prompt text is not approval or evidence",
            ],
            "next_safe_actions": [
                packet.get("next_owner_action"),
                "Do not commit secrets; do not fake Mode B",
            ],
            "human_review_required": True,
            "packet": packet,
        }
    )


def owner_unlock_demo_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_storage_claimed",
        "pen_test_passed_claimed",
        "customer_persistence_claimed",
        "mode_b_executed",
        "mode_b_ready",
        "fake_mode_b",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(owner_unlock_packet_invariant_failures(surface.get("packet") or {}))
    return fails

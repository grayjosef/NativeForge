"""Block 66 assembler: buyer trust surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate30_buyer_trust_surface_service import (
    build_buyer_trust_surfaces,
    buyer_trust_invariant_failures,
)

SCHEMA_VERSION = "nf_gate30_buyer_trust_assembler_v1"
DOCS = [
    "docs/operations/304_GATE30_BUYER_GRADE_UX_TRUST_SURFACES.md",
    "docs/operations/305_GATE30_FINAL_DEMO_TALK_TRACK_AND_TRUST_BOUNDARIES.md",
    "docs/operations/306_GATE30_POST_CAMPAIGN_NEXT_ACTIONS.md",
]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_buyer_trust_demo_surface() -> dict[str, Any]:
    result = build_buyer_trust_surfaces()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 66,
            "title": "Buyer-grade UX / trust surfaces",
            "docs": DOCS,
            "buyer_trust_contract": True,
            "views": result.get("views"),
            "safe_verbs": result.get("safe_verbs"),
            "talk_track": result.get("talk_track"),
            "controlled_customer_pilot_status": result.get(
                "controlled_customer_pilot_status"
            ),
            "production_rollout_status": result.get("production_rollout_status"),
            "login_live_claimed": False,
            "production_storage_claimed": False,
            "pen_test_passed_claimed": False,
            "fake_green_badge": False,
            "fake_pilot_ready_banner": False,
            "fake_production_ready": False,
            "blockers_exposed": True,
            "owner_next_action_exposed": True,
            "claim_freeze_visible": True,
            "demo_safe": True,
            "next_owner_action": result.get("next_owner_action"),
            "allowed_claims": result.get("allowed_claims"),
            "forbidden_claims": result.get("forbidden_claims"),
            "buyer_summary": [
                "Ten buyer/operator views answer what, why, who, blocked, next",
                "Claim freeze is visible on every primary panel",
                "No fake green badges, login live, storage live, or pen-test pass",
            ],
            "next_safe_actions": [
                result.get("next_owner_action"),
                "Use Review Eligibility / Build Evidence-Backed Package language only",
            ],
            "human_review_required": True,
            "result": result,
        }
    )


def buyer_trust_demo_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_storage_claimed",
        "pen_test_passed_claimed",
        "fake_green_badge",
        "fake_pilot_ready_banner",
        "fake_production_ready",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(buyer_trust_invariant_failures(surface.get("result") or {}))
    return fails

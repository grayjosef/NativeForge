"""Block 80 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate34_talk_track_service import (
    resolve_talk_track,
    talk_track_invariant_failures,
)

SCHEMA_VERSION = "nf_gate34_talk_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_talk_track_demo_surface() -> dict[str, Any]:
    result = resolve_talk_track()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 80,
            "title": "Buyer talk-track honesty",
            "buyer_talk_track_contract": True,
            "cta_safe": True,
            "fake_claim_language_blocked": True,
            "owner_action_exposed": result.get("owner_action_exposed"),
            "demo_narrative": result.get("evidence_backed_narrative"),
            "next_owner_action": result.get("owner_action_exposed"),
            "buyer_summary": [
                "Internal/demo route is GO; controlled pilot pending owner inputs",
                "Forbidden phrases stay blocked while claims are false",
            ],
            "next_safe_actions": ["Do not CTA customer access"],
            "result": result,
        }
    )


def talk_track_demo_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if surface.get("cta_safe") is False:
        fails.append("unsafe_cta")
    fails.extend(talk_track_invariant_failures(surface.get("result") or {}))
    return fails

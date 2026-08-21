"""Top-15 source validation demo assembler (Campaign Block 30)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.state_source_packet_service import (
    build_top15_state_source_packets,
    resolve_coverage_confidence,
    state_source_packet_invariant_failures,
)

SCHEMA_VERSION = "nf_top15_source_validation_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_top15_source_validation_demo_surface() -> dict[str, Any]:
    packets = build_top15_state_source_packets()
    resolutions = [resolve_coverage_confidence(p) for p in packets]
    sc = next(p for p in packets if p["state_code"] == "SC")
    non_sc_live = any(
        p.get("coverage_live_claimed") for p in packets if p["state_code"] != "SC"
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 30,
            "title": "Top-15 source research packets",
            "packets": packets,
            "resolutions": resolutions,
            "packet_count": len(packets),
            "states_packeted": [p["state_code"] for p in packets],
            "active_customer_lane": "SC",
            "sc_packet": {
                "source_status": sc.get("source_status"),
                "freshness_status": sc.get("freshness_status"),
                "validation_status": sc.get("validation_status"),
                "confidence": sc.get("confidence"),
                "coverage_live_claimed": sc.get("coverage_live_claimed"),
            },
            "buyer_summary": [
                "Top-15 source research packets exist for all provisional states",
                "SC remains curated-current demo lane; live multi-state coverage not claimed",
                "Non-SC packets are honest needs_research / unknown-heavy",
                "Coverage confidence resolver exposes blockers and next actions",
            ],
            "non_sc_live_coverage_claimed": bool(non_sc_live),
            "all_top15_live_claimed": False,
            "all_portals_integrated_claimed": False,
            "final_eligibility_claimed": False,
            "live_national_coverage_complete_claimed": False,
            "human_review_required": True,
        }
    )


def top15_source_validation_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "non_sc_live_coverage_claimed",
        "all_top15_live_claimed",
        "all_portals_integrated_claimed",
        "final_eligibility_claimed",
        "live_national_coverage_complete_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("packet_count") != 15:
        fails.append(f"packet_count:{surface.get('packet_count')}")
    for p in surface.get("packets") or []:
        fails.extend(state_source_packet_invariant_failures(p))
    sc = surface.get("sc_packet") or {}
    if sc.get("coverage_live_claimed") is True:
        fails.append("sc_live_claimed_without_live_check")
    return fails

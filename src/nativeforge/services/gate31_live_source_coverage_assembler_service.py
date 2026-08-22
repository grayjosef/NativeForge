"""Block 68 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate31_live_source_coverage_service import (
    live_source_coverage_invariant_failures,
    resolve_live_source_coverage,
)

SCHEMA_VERSION = "nf_gate31_source_coverage_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_live_source_coverage_demo_surface() -> dict[str, Any]:
    result = resolve_live_source_coverage()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 68,
            "title": "Live source coverage / Top-15 execution path",
            "source_coverage_execution_contract": True,
            "source_packets_mapped": result.get("source_packets_mapped"),
            "read_only_checks_attempted": result.get("read_only_checks_attempted"),
            "top15_states": result.get("top15_states"),
            "sc_status": result.get("sc_status"),
            "non_sc_status": result.get("non_sc_status"),
            "freshness_resolver": True,
            "confidence_resolver": True,
            "duplicate_detection": True,
            "live_coverage_claimed": False,
            "top15_live_claimed": False,
            "broad_coverage_claimed": False,
            "missing_gates": result.get("missing_gates"),
            "next_owner_action": "Run read-only checks per Top-15 source; attach evidence refs",
            "buyer_summary": [
                "Packets mapped for Top-15; packet_only is not live coverage",
                "SC remains demo-current; Top-15 live and broad coverage stay false",
            ],
            "next_safe_actions": ["Do not claim all-state or Top-15 live coverage"],
            "result": result,
        }
    )


def live_source_coverage_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "live_coverage_claimed",
        "top15_live_claimed",
        "broad_coverage_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(live_source_coverage_invariant_failures(surface.get("result") or {}))
    return fails

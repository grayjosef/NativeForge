"""Block 71 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate32_source_freshness_service import (
    run_source_freshness_bundle,
    source_freshness_invariant_failures,
)

SCHEMA_VERSION = "nf_gate32_freshness_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_source_freshness_demo_surface() -> dict[str, Any]:
    result = run_source_freshness_bundle()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 71,
            "title": "Source freshness / dedupe read-only checks",
            "source_freshness_contract": True,
            "read_only_checks_attempted": False,
            "live_source_claim": False,
            "top15_live_claimed": False,
            "broad_coverage_claimed": False,
            "duplicate_detector": True,
            "missing_gates": result.get("missing_gates"),
            "next_owner_action": "Run safe read-only probes; do not claim live coverage from packets",
            "buyer_summary": [
                "Top-15 packets remain packet_only until probes run",
                "Duplicate detector exists; live/Top-15/broad coverage stay false",
            ],
            "next_safe_actions": ["Do not claim fresh or live from packet_only"],
            "result": result,
        }
    )


def source_freshness_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in ("live_source_claim", "top15_live_claimed", "broad_coverage_claimed"):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(source_freshness_invariant_failures(surface.get("result") or {}))
    return fails

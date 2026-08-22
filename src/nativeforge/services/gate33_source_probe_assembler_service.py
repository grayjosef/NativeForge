"""Block 75 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate33_source_probe_service import (
    run_source_probe_bundle,
    source_probe_invariant_failures,
)

SCHEMA_VERSION = "nf_gate33_probe_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_source_probe_demo_surface() -> dict[str, Any]:
    result = run_source_probe_bundle()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 75,
            "title": "Safe read-only source probes",
            "source_probe_contract": True,
            "read_only_probes_attempted": result.get("read_only_probes_attempted"),
            "sources_probed": result.get("sources_probed"),
            "live_source_claim": False,
            "top15_live_claimed": False,
            "broad_coverage_claimed": False,
            "evidence_refs": result.get("evidence_refs"),
            "missing_gates": ["network_probes_not_run", "top15_not_live"],
            "next_owner_action": "Do not treat allowlisted local probe as live coverage",
            "buyer_summary": [
                "Allowlisted local probe may be attempted; others stay packet-only",
                "No live / Top-15 / broad coverage claim",
            ],
            "next_safe_actions": ["Do not claim reachable from packet-only sources"],
            "result": result,
        }
    )


def source_probe_demo_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in ("live_source_claim", "top15_live_claimed", "broad_coverage_claimed"):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(source_probe_invariant_failures(surface.get("result") or {}))
    return fails

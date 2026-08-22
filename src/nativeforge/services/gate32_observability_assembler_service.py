"""Block 72 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate32_observability_service import (
    observability_invariant_failures,
    resolve_observability,
)

SCHEMA_VERSION = "nf_gate32_obs_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_observability_demo_surface() -> dict[str, Any]:
    result = resolve_observability()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 72,
            "title": "Observability / readiness for controlled pilot ops",
            "observability_contract": True,
            "health_checks": False,
            "alert_readiness": result.get("alert_readiness"),
            "alert_sent_claimed": False,
            "pilot_ops_readiness": False,
            "production_monitoring_claimed": False,
            "controlled_pilot_status": "CONDITIONAL_INTERNAL_ONLY",
            "missing_gates": result.get("missing_gates"),
            "next_owner_action": "Add healthchecks and support owner before claiming ops ready",
            "buyer_summary": [
                "Workflows are smoke_only, not production monitored",
                "Alert sent remains false; pilot ops readiness false",
            ],
            "next_safe_actions": ["Do not claim monitored or alert sent"],
            "result": result,
        }
    )


def observability_demo_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "alert_sent_claimed",
        "pilot_ops_readiness",
        "production_monitoring_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(observability_invariant_failures(surface.get("result") or {}))
    return fails

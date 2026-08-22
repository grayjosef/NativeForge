"""Block 76 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate33_healthcheck_service import (
    healthcheck_invariant_failures,
    resolve_healthchecks,
)

SCHEMA_VERSION = "nf_gate33_hc_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_healthcheck_demo_surface() -> dict[str, Any]:
    result = resolve_healthchecks()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 76,
            "title": "Healthcheck + error-budget instrumentation",
            "healthcheck_registry": True,
            "healthcheck_passed": result.get("healthcheck_passed"),
            "healthcheck_failed": result.get("healthcheck_failed"),
            "error_budget": result.get("error_budget"),
            "alert_readiness": result.get("alert_readiness"),
            "alert_sent_claimed": False,
            "pilot_ops_readiness": False,
            "production_monitoring_claimed": False,
            "controlled_pilot_status": "CONDITIONAL_INTERNAL_ONLY",
            "missing_gates": result.get("missing_gates"),
            "next_owner_action": "Healthcheck-ready is not production monitoring",
            "buyer_summary": [
                "Registry exists; auth/storage remain blocked_missing_config",
                "Alert sent remains false; pilot ops readiness false",
            ],
            "next_safe_actions": ["Do not claim monitored or alert sent"],
            "result": result,
        }
    )


def healthcheck_demo_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "alert_sent_claimed",
        "pilot_ops_readiness",
        "production_monitoring_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(healthcheck_invariant_failures(surface.get("result") or {}))
    return fails

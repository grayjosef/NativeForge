"""Whether any source is actually live.

A collector is live only when every production gate is true for that source.
An empty measurement is not a live fleet. This module does not fetch, does
not mint a warrant, and does not start a scheduler.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_fleet_live_readiness_v1"

LIVE_GATES: tuple[str, ...] = (
    "registered",
    "enabled",
    "authorized",
    "warrant_valid",
    "terms_satisfied",
    "transport_healthy",
    "parser_healthy",
    "normalization_healthy",
    "persistence_healthy",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def source_gates_are_live(gates: dict[str, Any] | None) -> bool:
    evidence = gates or {}
    return all(evidence.get(gate) is True for gate in LIVE_GATES)


def derive_collectors_live(
    *,
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Count sources whose gate evidence is complete.

    ``sources is None`` means nobody measured the fleet. That is zero live
    collectors, not an assumption that collection is forbidden by a constant.
    """
    measured = sources is not None
    rows = list(sources or [])
    live_ids: list[str] = []
    for row in rows:
        if not source_gates_are_live(
            row.get("gates") if isinstance(row, dict) else None
        ):
            continue
        source_id = str((row or {}).get("source_id") or "").strip()
        if source_id and source_id not in live_ids:
            live_ids.append(source_id)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "measured": measured,
            "collectors_live": len(live_ids),
            "fleet_live_sources": live_ids,
            "live_gates": list(LIVE_GATES),
            "live_fetch_performed": False,
            "fabricated": False,
        }
    )

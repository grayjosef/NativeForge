"""Source freshness / dedupe read-only checks (Block 71)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate31_live_source_coverage_service import (
    detect_duplicate_opportunities,
)

SCHEMA_VERSION = "nf_gate32_source_freshness_v1"

HEALTH_STATUSES = (
    "not_started",
    "packet_only",
    "probe_available",
    "probe_attempted",
    "reachable",
    "unreachable",
    "fresh",
    "stale",
    "partial",
    "error",
    "validated_demo_only",
    "validated_live_read_only",
    "blocked",
    "unknown",
)

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def canonical_opportunity_id(row: dict[str, Any]) -> str:
    return str(
        row.get("opportunity_id") or row.get("canonical_id") or row.get("title") or ""
    )


def resolve_source_health(
    *,
    source_id: str,
    state: str,
    source_name: str,
    source_type: str = "state_portal",
    packet_only: bool = True,
    probe_available: bool = False,
    probe_attempted: bool = False,
    reachable: bool = False,
    stale: bool = True,
    error: str | None = None,
    evidence_ref: str | None = None,
    last_checked_at: str | None = None,
    last_seen_opportunity_at: str | None = None,
    duplicate_count: int = 0,
) -> dict[str, Any]:
    missing: list[str] = []
    status = "packet_only" if packet_only else "not_started"
    if probe_available and not probe_attempted:
        status = "probe_available"
    if probe_attempted:
        status = "probe_attempted"
        if error:
            status = "error"
        elif reachable:
            status = "stale" if stale else "reachable"
        else:
            status = "unreachable"
    if not evidence_ref:
        missing.append("evidence_ref")
    if error:
        missing.append("probe_error")
    live = bool(
        not packet_only
        and probe_attempted
        and reachable
        and not stale
        and not error
        and evidence_ref
    )
    if live:
        status = "validated_live_read_only"
    freshness = "stale" if (stale or packet_only or not reachable) else "fresh"
    if error:
        freshness = "error"
    _AUDIT.append({"event": "source_freshness_check", "source_id": source_id})
    return _json_safe(
        {
            "source_id": source_id,
            "state": state,
            "source_name": source_name,
            "source_type": source_type,
            "probe_attempted": probe_attempted,
            "reachable": bool(reachable and probe_attempted and not error),
            "freshness_status": freshness,
            "last_checked_at": last_checked_at,
            "last_seen_opportunity_at": last_seen_opportunity_at,
            "evidence_ref": evidence_ref,
            "error": error,
            "duplicate_count": duplicate_count,
            "status": status,
            "live_coverage_claimed": live,
            "broad_coverage_claimed": False,
            "missing_gates": missing,
        }
    )


def run_source_freshness_bundle(
    *,
    rows: list[dict[str, Any]] | None = None,
    opportunity_fixtures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    mapped = rows or [
        resolve_source_health(
            source_id=f"pkt-{st}",
            state=st,
            source_name=f"{st}_packet",
            packet_only=True,
            evidence_ref=f"packet:{st}",
        )
        for st in (
            "SC",
            "OK",
            "AZ",
            "NM",
            "AK",
            "CA",
            "WA",
            "OR",
            "MT",
            "SD",
            "ND",
            "MN",
            "WI",
            "NC",
            "HI",
        )
    ]
    fixtures = opportunity_fixtures or []
    dups = detect_duplicate_opportunities(fixtures)
    live_rows = [r for r in mapped if r.get("live_coverage_claimed")]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_freshness_contract": True,
            "read_only_checks_attempted": any(r.get("probe_attempted") for r in mapped),
            "sources_checked": len(mapped),
            "reachable_count": sum(1 for r in mapped if r.get("reachable")),
            "fresh_count": sum(
                1 for r in mapped if r.get("freshness_status") == "fresh"
            ),
            "stale_count": sum(
                1 for r in mapped if r.get("freshness_status") == "stale"
            ),
            "error_count": sum(1 for r in mapped if r.get("error")),
            "duplicate_detector": True,
            "duplicate_count": len(dups),
            "duplicate_ids": dups,
            "canonical_ids": [canonical_opportunity_id(x) for x in fixtures],
            "health_statuses": list(HEALTH_STATUSES),
            "rows": mapped,
            "live_row_count": len(live_rows),
            "live_source_claim": False,
            "top15_live_claimed": False,
            "broad_coverage_claimed": False,
            "audit_events": True,
            "audit_refs": [a["event"] for a in _AUDIT[-5:]],
            "missing_gates": ["probes_not_run_mode_a", "top15_not_live"],
        }
    )


def source_freshness_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in ("live_source_claim", "top15_live_claimed", "broad_coverage_claimed"):
        if result.get(key) is True:
            fails.append(key)
    return fails


def clear_source_freshness_audit_for_tests() -> None:
    _AUDIT.clear()

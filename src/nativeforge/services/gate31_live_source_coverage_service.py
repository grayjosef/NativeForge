"""Live source coverage / Top-15 validation execution path (Block 68)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_gate31_live_source_coverage_v1"

TOP15 = (
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

SOURCE_STATUSES = (
    "not_started",
    "packet_only",
    "read_only_check_available",
    "read_only_check_attempted",
    "reachable",
    "unreachable",
    "fresh",
    "stale",
    "needs_manual_review",
    "validated_for_demo",
    "validated_live",
    "blocked",
    "unknown",
)

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def detect_duplicate_opportunities(rows: list[dict[str, Any]]) -> list[str]:
    seen: dict[str, int] = {}
    dups: list[str] = []
    for row in rows:
        key = str(row.get("opportunity_id") or row.get("title") or "")
        if not key:
            continue
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 2:
            dups.append(key)
    return dups


def resolve_source_row(
    *,
    state: str,
    source_name: str,
    source_type: str = "state_portal",
    packet_only: bool = True,
    reachable: bool = False,
    stale: bool = True,
    error: bool = False,
    evidence_ref: str | None = None,
    last_checked_at: str | None = None,
) -> dict[str, Any]:
    missing: list[str] = []
    status = "packet_only" if packet_only else "not_started"
    if reachable and not packet_only:
        status = "stale" if stale else "reachable"
    if error:
        status = "blocked"
        missing.append("source_error")
    if not evidence_ref:
        missing.append("evidence_ref")
    live = bool(
        not packet_only and reachable and not stale and not error and evidence_ref
    )
    if live:
        status = "validated_live"
    freshness = (
        "stale" if stale or packet_only else ("fresh" if reachable else "unknown")
    )
    confidence = "low" if packet_only or error else ("medium" if reachable else "low")
    return {
        "state": state,
        "source_name": source_name,
        "source_type": source_type,
        "reachability_status": "reachable"
        if reachable and not error
        else ("unreachable" if error else "unknown"),
        "freshness_status": freshness,
        "confidence": confidence,
        "last_checked_at": last_checked_at,
        "evidence_ref": evidence_ref,
        "status": status,
        "live_coverage_claimed": live,
        "broad_coverage_claimed": False,
        "missing_gates": missing,
    }


def resolve_live_source_coverage(
    *,
    rows: list[dict[str, Any]] | None = None,
    opportunity_fixtures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    mapped = rows or [
        resolve_source_row(
            state=st,
            source_name=f"{st}_packet",
            packet_only=True,
            evidence_ref=f"packet:{st}",
        )
        for st in TOP15
    ]
    live_states = [r["state"] for r in mapped if r.get("live_coverage_claimed")]
    top15_live = bool(
        len(live_states) == len(TOP15) and all(st in live_states for st in TOP15)
    )
    dups = detect_duplicate_opportunities(opportunity_fixtures or [])
    sc = next((r for r in mapped if r["state"] == "SC"), {})
    _AUDIT.append({"event": "source_coverage_resolve", "live_states": live_states})
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_coverage_execution_contract": True,
            "source_packets_mapped": len(mapped),
            "read_only_checks_attempted": any(
                r.get("status") not in {"packet_only", "not_started"} for r in mapped
            ),
            "top15_states": list(TOP15),
            "source_statuses": list(SOURCE_STATUSES),
            "rows": mapped,
            "sc_status": sc.get("status") or "packet_only",
            "non_sc_status": "packet_only",
            "freshness_resolver": True,
            "confidence_resolver": True,
            "duplicate_opportunity_ids": dups,
            "duplicate_detection": True,
            "live_coverage_claimed": False,
            "top15_live_claimed": top15_live,
            "broad_coverage_claimed": False,
            "missing_gates": ["top15_not_all_live", "packet_only_majority"],
            "live_states": live_states,
            "audit_refs": [a["event"] for a in _AUDIT[-3:]],
        }
    )


def live_source_coverage_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("broad_coverage_claimed") is True:
        fails.append("broad_coverage")
    if result.get("top15_live_claimed") and len(result.get("live_states") or []) < 15:
        fails.append("top15_without_all_states")
    if result.get("live_coverage_claimed") is True and result.get("mode") == "A":
        fails.append("live_coverage_mode_a")
    return fails


def clear_source_coverage_audit_for_tests() -> None:
    _AUDIT.clear()

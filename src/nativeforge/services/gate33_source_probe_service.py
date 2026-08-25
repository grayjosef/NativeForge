"""Safe read-only source probes with evidence refs (Block 75)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
    new_collector,
)
from nativeforge.services.gate31_live_source_coverage_service import (
    detect_duplicate_opportunities,
)
from nativeforge.services.gate32_source_freshness_service import (
    canonical_opportunity_id,
)

SCHEMA_VERSION = "nf_gate33_source_probe_v1"
SAFE_PROBE_ALLOWLIST = frozenset({"pkt-SC", "local-fixture-sc"})

def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_safe_probe(
    *,
    source_id: str,
    state: str,
    source_name: str,
    source_url_or_reference: str = "packet-only",
    allowlist: frozenset[str] | None = None,
    attempt: bool = True,
    fail: bool = False,
    reachable: bool = False,
    stale: bool = True,
    evidence_ref: str | None = None,
    network_used: bool = False,
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    allowed_set = allowlist if allowlist is not None else SAFE_PROBE_ALLOWLIST
    probe_allowed = source_id in allowed_set
    probe_attempted = bool(attempt and probe_allowed and not network_used)
    error = "probe_failed" if (probe_attempted and fail) else None
    if not probe_allowed:
        probe_attempted = False
    if network_used:
        error = "network_probe_not_run_mode_a"
        probe_attempted = False
    missing: list[str] = []
    if probe_attempted and not evidence_ref:
        missing.append("evidence_ref")
    reachable_ok = bool(
        probe_attempted and reachable and not error and not network_used
    )
    freshness = "unknown"
    if probe_attempted and error:
        freshness = "error"
    elif not probe_attempted:
        freshness = "packet_only"
    elif reachable_ok and stale:
        freshness = "stale"
    elif reachable_ok and not stale:
        freshness = "fresh"
    else:
        freshness = "unreachable"
    live = bool(
        probe_attempted
        and reachable_ok
        and not stale
        and not error
        and evidence_ref
        and freshness == "fresh"
    )
    run_id = f"nf_probe_{uuid.uuid4().hex[:10]}"
    collector.add({"event": "safe_source_probe", "source_id": source_id})
    return _json_safe(
        {
            "probe_run_id": run_id,
            "source_id": source_id,
            "state": state,
            "source_name": source_name,
            "source_url_or_reference": source_url_or_reference,
            "probe_allowed": probe_allowed,
            "probe_attempted": probe_attempted,
            "reachable": reachable_ok,
            "freshness_status": freshness,
            "last_checked_at": datetime.now(UTC).isoformat()
            if probe_attempted
            else None,
            "evidence_ref": evidence_ref if probe_attempted else None,
            "error": error,
            "confidence": "low_mode_a",
            "live_coverage_claimed": live,
            "top15_live_claimed": False,
            "broad_coverage_claimed": False,
            "missing_gates": missing,
            "network_used": False,
        }
    )


def run_source_probe_bundle(
    *,
    rows: list[dict[str, Any]] | None = None,
    opportunity_fixtures: list[dict[str, Any]] | None = None,
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    mapped = rows or [
        run_safe_probe(
            collector=collector,
            source_id="pkt-SC",
            state="SC",
            source_name="SC packet allowlist",
            source_url_or_reference="local://packet/SC",
            attempt=True,
            fail=False,
            reachable=False,
            evidence_ref="nf://gate33/probe/pkt-SC",
        ),
        *[
            run_safe_probe(
            collector=collector,
                source_id=f"pkt-{st}",
                state=st,
                source_name=f"{st}_packet",
                attempt=True,
                evidence_ref=None,
            )
            for st in (
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
        ],
    ]
    fixtures = opportunity_fixtures or []
    dups = detect_duplicate_opportunities(fixtures)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_probe_contract": True,
            "read_only_probes_attempted": any(r.get("probe_attempted") for r in mapped),
            "sources_probed": sum(1 for r in mapped if r.get("probe_attempted")),
            "reachable_count": sum(1 for r in mapped if r.get("reachable")),
            "fresh_count": sum(
                1 for r in mapped if r.get("freshness_status") == "fresh"
            ),
            "stale_count": sum(
                1 for r in mapped if r.get("freshness_status") == "stale"
            ),
            "error_count": sum(1 for r in mapped if r.get("error")),
            "evidence_refs": [
                r.get("evidence_ref") for r in mapped if r.get("evidence_ref")
            ],
            "duplicate_detector": True,
            "duplicate_ids": dups,
            "canonical_ids": [canonical_opportunity_id(x) for x in fixtures],
            "rows": mapped,
            "live_source_claim": False,
            "top15_live_claimed": False,
            "broad_coverage_claimed": False,
            "packet_only_remaining": [
                r["source_id"] for r in mapped if not r.get("probe_attempted")
            ],
            "audit_refs": collector.event_names(8),
        }
    )


def source_probe_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in ("live_source_claim", "top15_live_claimed", "broad_coverage_claimed"):
        if result.get(key) is True:
            fails.append(key)
    return fails

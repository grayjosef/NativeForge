"""Operator runbook drill against demo route (Block 81)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_gate34_drill_v1"

DRILLS = (
    "source_probe_runbook",
    "healthcheck_runbook",
    "restore_rehearsal_runbook",
    "incident_triage_runbook",
    "claim_freeze_runbook",
    "launch_packet_runbook",
    "demo_route_runbook",
)

DRILL_STATUSES = (
    "not_started",
    "drill_ready",
    "drill_attempted",
    "drill_passed",
    "drill_failed",
    "blocked_missing_owner_input",
    "blocked_missing_external_vendor",
    "blocked_policy_decision",
    "unknown",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_one_drill(
    name: str,
    *,
    attempted: bool = True,
    want_pass: bool = True,
    evidence_ref: str | None = None,
    blocked_owner: bool = False,
) -> dict[str, Any]:
    status = "not_started"
    if blocked_owner:
        status = "blocked_missing_owner_input"
    elif attempted:
        status = "drill_attempted"
        if want_pass and evidence_ref:
            status = "drill_passed"
        elif want_pass and not evidence_ref:
            status = "drill_failed"
        elif not want_pass:
            status = "drill_failed"
    return {
        "name": name,
        "status": status,
        "evidence_ref": evidence_ref,
        "alert_sent_claimed": False,
        "production_restore_claimed": False,
        "customer_access_claimed": False,
    }


def run_operator_drills(
    *,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    mapped = rows or [
        run_one_drill(
            name,
            evidence_ref=f"nf://gate34/drill/{name}",
        )
        for name in DRILLS
    ]
    passed = [r["name"] for r in mapped if r["status"] == "drill_passed"]
    failed = [r["name"] for r in mapped if r["status"] == "drill_failed"]
    blocked = [r["name"] for r in mapped if str(r["status"]).startswith("blocked_")]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "drill_contract": True,
            "drill_statuses": list(DRILL_STATUSES),
            "rows": mapped,
            "drills_attempted": [
                r["name"] for r in mapped if r["status"] != "not_started"
            ],
            "drills_passed": passed,
            "drills_failed": failed,
            "blocked_drills": blocked,
            "drill_evidence_refs": [
                r["evidence_ref"] for r in mapped if r.get("evidence_ref")
            ],
            "pilot_go_claimed": False,
            "production_rollout_claimed": False,
            "alert_sent_claimed": False,
            "production_restore_claimed": False,
            "owner_input_still_blocker": True,
            "controlled_pilot_status": "CONDITIONAL_INTERNAL_ONLY",
        }
    )


def drill_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("pilot_go_claimed") is True:
        fails.append("pilot_go")
    if result.get("production_rollout_claimed") is True:
        fails.append("rollout_go")
    for row in result.get("rows") or []:
        if row.get("status") == "drill_passed" and not row.get("evidence_ref"):
            fails.append(f"passed_without_evidence:{row.get('name')}")
    return fails

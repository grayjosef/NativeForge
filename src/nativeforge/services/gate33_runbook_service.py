"""Operator runbooks + remaining non-owner checklist (Block 78)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_gate33_runbooks_v1"

CHECK_STATUSES = (
    "complete",
    "partially_complete",
    "blocked_owner_input",
    "blocked_external_vendor",
    "blocked_policy_decision",
    "still_actionable_without_owner",
    "not_started",
    "unknown",
)

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_runbooks_and_checklist(
    *,
    login_live: bool = False,
    production_storage: bool = False,
    pen_test_passed: bool = False,
) -> dict[str, Any]:
    runbooks = {
        "index": True,
        "controlled_pilot": True,
        "source_probe": True,
        "healthcheck": True,
        "restore_rehearsal": True,
        "incident_triage": True,
    }
    checklist = [
        {
            "id": "source_probe_allowlist",
            "status": "partially_complete",
            "lane": "non_owner",
            "evidence_ref": "nf://gate33/probe/pkt-SC",
        },
        {
            "id": "healthcheck_registry",
            "status": "partially_complete",
            "lane": "non_owner",
            "evidence_ref": "nf://gate33/healthcheck-registry",
        },
        {
            "id": "non_prod_restore_model",
            "status": "partially_complete",
            "lane": "non_owner",
            "evidence_ref": "nf://gate33/non-prod-restore-rehearsal",
        },
        {
            "id": "operator_runbooks",
            "status": "complete",
            "lane": "non_owner",
            "evidence_ref": "docs/operations/321_GATE33_OPERATOR_RUNBOOKS.md",
        },
        {
            "id": "auth0_oidc",
            "status": "blocked_owner_input",
            "lane": "owner",
            "evidence_ref": None,
        },
        {
            "id": "storage_approval",
            "status": "blocked_owner_input",
            "lane": "owner",
            "evidence_ref": None,
        },
        {
            "id": "pen_test",
            "status": "blocked_external_vendor",
            "lane": "external",
            "evidence_ref": None,
        },
        {
            "id": "remaining_local_docs",
            "status": "still_actionable_without_owner",
            "lane": "non_owner",
            "evidence_ref": None,
        },
    ]
    owner = [c for c in checklist if c["lane"] == "owner"]
    non_owner = [c for c in checklist if c["lane"] == "non_owner"]
    external = [c for c in checklist if c["lane"] == "external"]
    for item in checklist:
        if item["status"] == "complete" and not item.get("evidence_ref"):
            item["status"] = "partially_complete"
    hard_blocked = not (login_live and production_storage and pen_test_passed)
    _AUDIT.append({"event": "runbook_resolve"})
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "runbook_index": runbooks,
            "checklist_statuses": list(CHECK_STATUSES),
            "checklist": checklist,
            "owner_gated_blockers": [c["id"] for c in owner],
            "non_owner_items": [c["id"] for c in non_owner],
            "external_vendor_blockers": [c["id"] for c in external],
            "still_actionable_without_owner": [
                c["id"]
                for c in checklist
                if c["status"] == "still_actionable_without_owner"
            ],
            "controlled_customer_pilot_status": "CONDITIONAL_INTERNAL_ONLY",
            "production_rollout_status": "PRODUCTION_ROLLOUT_NO_GO",
            "pilot_go_claimed": False,
            "production_rollout_go_claimed": False,
            "hard_gates_remain": hard_blocked,
            "next_action_sequence": [
                "Keep probing only allowlisted sources without network",
                "Staff support owner (non-owner org action)",
                "Owner: OIDC_* OOB",
                "Owner: storage approval/config",
                "External: pen-test report",
            ],
            "allowed_claims": [
                "monday_demo_go",
                "non_prod_restore_model",
                "healthcheck_registry_exists",
                "allowlisted_local_probe_attempted",
            ],
            "forbidden_claims": [
                "controlled_customer_pilot_go",
                "production_rollout_go",
                "login_live",
                "production_restore",
                "alert_sent",
                "top15_live",
            ],
            "post_gate33_recommendation": "Gate 34: owner-input rehearsal freeze + remaining honesty UX",
        }
    )


def runbook_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("pilot_go_claimed") is True:
        fails.append("pilot_go")
    if result.get("production_rollout_go_claimed") is True:
        fails.append("rollout_go")
    if "auth0_oidc" not in (result.get("owner_gated_blockers") or []):
        fails.append("owner_not_gated")
    for item in result.get("checklist") or []:
        if item.get("status") == "complete" and not item.get("evidence_ref"):
            fails.append(f"complete_without_evidence:{item.get('id')}")
    return fails

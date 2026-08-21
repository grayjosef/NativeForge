"""Pen-test scheduling packet + blocker burn-down (Block 38)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_pen_test_scheduling_burndown_v1"
DOC_ARTIFACT = "docs/operations/208_PEN_TEST_SCHEDULING_AND_BLOCKER_BURNDOWN.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_pen_test_scheduling_and_burndown() -> dict[str, Any]:
    blockers = [
        {
            "blocker": "external_auth_not_configured",
            "severity": "critical",
            "owner": "Mayhem",
            "next_action": "Approve Auth0/OIDC + provision secrets",
            "can_complete_before_sunday": True,
            "customer_pilot_impact": "blocks GO",
            "production_impact": "blocks production auth",
        },
        {
            "blocker": "production_storage_not_approved",
            "severity": "critical",
            "owner": "Mayhem",
            "next_action": "Sign owner approval packet 206",
            "can_complete_before_sunday": True,
            "customer_pilot_impact": "blocks GO",
            "production_impact": "blocks persistence",
        },
        {
            "blocker": "pen_test_not_scheduled",
            "severity": "high",
            "owner": "Mayhem / vendor",
            "next_action": "Pick window + vendor; use this packet",
            "can_complete_before_sunday": True,
            "customer_pilot_impact": "blocks GO",
            "production_impact": "blocks rollout",
        },
        {
            "blocker": "python_sca_incomplete_or_findings",
            "severity": "high",
            "owner": "build_agent",
            "next_action": "Run/remediate pip-audit under Gate 16 path",
            "can_complete_before_sunday": True,
            "customer_pilot_impact": "blocks GO if high/critical remain",
            "production_impact": "blocks secure claim",
        },
        {
            "blocker": "live_authority_verification",
            "severity": "medium",
            "owner": "Mayhem",
            "next_action": "Approve read-only SAM/AOR clients",
            "can_complete_before_sunday": False,
            "customer_pilot_impact": "limits submit authority",
            "production_impact": "limits authority claims",
        },
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact": DOC_ARTIFACT,
            "recommended_test_window": "Friday–Saturday before Sunday readiness gate",
            "route_api_inventory_reference": [
                "/?view=sc_customer_demo",
                "/api/*",
                "docs/operations/189_EXTERNAL_PEN_TEST_EXECUTION_PACKET.md",
            ],
            "test_accounts_needed": [
                "operator fixture account",
                "customer org A fixture",
                "customer org B fixture (cross-org deny)",
            ],
            "seed_data_needed": [
                "SC curated demo pack",
                "multi-org cohort fixtures",
                "evidence intake samples",
            ],
            "auth_storage_status": {
                "login_live": False,
                "external_auth_configured": False,
                "production_storage_validated": False,
            },
            "out_of_scope": [
                "collaboration matching (dark/OFF)",
                "live SAM/AOR verification",
                "production customer data mutation",
            ],
            "known_blockers": [b["blocker"] for b in blockers],
            "pre_test_checklist": [
                "RBAC denial suite green",
                "tenant isolation suite green",
                "demo route smoke green",
                "no secrets in repo",
                "storage claims remain honest",
            ],
            "remediation_workflow": [
                "Triage by severity",
                "Fix scoped issues only",
                "Re-run smoke + denial suites",
                "Do not claim pen-test passed until vendor sign-off",
            ],
            "owner_vendor_action_required": True,
            "pen_test_passed_claimed": False,
            "pen_test_scheduled_claimed": False,
            "blocker_burndown": blockers,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "human_review_required": True,
        }
    )


def pen_test_scheduling_invariant_failures(packet: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in ("pen_test_passed_claimed", "pen_test_scheduled_claimed"):
        if packet.get(key) is True:
            fails.append(key)
    if packet.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    if not (packet.get("blocker_burndown") or []):
        fails.append("no_burndown")
    return fails

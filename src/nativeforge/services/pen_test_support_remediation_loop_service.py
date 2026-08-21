"""Pen-test support and remediation loop (Block 40)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_pen_test_support_remediation_loop_v1"
DOC = "docs/operations/214_PEN_TEST_SUPPORT_AND_REMEDIATION_LOOP.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_pen_test_support_remediation_loop() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact": DOC,
            "pen_test_status": "not_started",
            "test_window": "owner_scheduled_TBD",
            "scope": [
                "/?view=sc_customer_demo",
                "/api/*",
                "RBAC denial paths",
                "tenant isolation paths",
            ],
            "test_accounts": [
                "operator fixture",
                "customer org A",
                "customer org B",
            ],
            "seed_data": [
                "SC curated demo pack",
                "multi-org cohort",
                "evidence intake samples",
            ],
            "auth_storage_status": {
                "login_live": False,
                "external_auth_configured": False,
                "production_storage_validated": False,
            },
            "current_no_go_claims": [
                "login_live",
                "production_storage_validated",
                "controlled_customer_pilot_GO",
                "pen_test_passed",
            ],
            "findings": [],
            "finding_severity_levels": ["critical", "high", "medium", "low", "info"],
            "remediation_owner": "build_agent_with_owner_approval",
            "remediation_status": "idle_awaiting_test_start",
            "retest_status": "not_applicable",
            "pass_claim_rules": [
                "pen_test_passed_claimed=true only after vendor/owner sign-off",
                "Do not claim production-ready from pen-test alone",
                "High/critical findings block pilot GO until remediated+retested",
            ],
            "remediation_workflow": [
                "Ingest finding with severity + owner",
                "Scoped fix only; no mass dependency churn",
                "Re-run denial/tenant/smoke suites",
                "Mark remediated; request retest",
                "Update operator panel honestly",
            ],
            "pen_test_passed_claimed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "human_review_required": True,
        }
    )


def pen_test_support_loop_invariant_failures(loop: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if loop.get("pen_test_passed_claimed") is True:
        fails.append("pen_test_passed_claimed")
    if loop.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    if loop.get("pen_test_status") == "passed":
        fails.append("status_passed_without_claim_check")
    return fails

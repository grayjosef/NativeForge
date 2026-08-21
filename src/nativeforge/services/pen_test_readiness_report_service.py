"""Pen-test readiness report (Gate 06 / Block 18). Does NOT claim pen-test pass."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.adversarial_fixture_service import run_adversarial_suite
from nativeforge.services.code_health_inventory_service import (
    build_code_health_inventory,
)
from nativeforge.services.critical_path_coverage_map_service import (
    build_critical_path_coverage_map,
)
from nativeforge.services.data_isolation_bypass_suite_service import (
    run_data_isolation_and_bypass_suite,
)
from nativeforge.services.no_fail_invariant_suite_service import (
    run_no_fail_invariant_suite,
)
from nativeforge.services.security_posture_inventory_service import (
    build_security_posture_inventory,
)

SCHEMA_VERSION = "nf_pen_test_readiness_report_v1"


def build_pen_test_readiness_report() -> dict[str, Any]:
    inventory = build_code_health_inventory()
    coverage = build_critical_path_coverage_map()
    posture = build_security_posture_inventory()
    invariants = run_no_fail_invariant_suite()
    adversarial = run_adversarial_suite()
    isolation = run_data_isolation_and_bypass_suite()
    ready_enough_for_external_pen_test_planning = (
        invariants.get("overall_status") == "PASS"
        and adversarial.get("overall_status") == "PASS"
        and isolation.get("overall_status") == "PASS"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_block": 18,
        "title": "NativeForge pen-test readiness evidence (not a pass certificate)",
        "pen_test_passed_claimed": False,
        "production_secure_claimed": False,
        "ready_for_external_pen_test_engagement_planning": ready_enough_for_external_pen_test_planning,
        "evidence_pack": {
            "code_health_totals": inventory.get("totals"),
            "critical_path_weakest": coverage.get("weakest_areas"),
            "security_posture_counts": posture.get("status_counts"),
            "no_fail_invariants_status": invariants.get("overall_status"),
            "adversarial_suite_status": adversarial.get("overall_status"),
            "isolation_bypass_status": isolation.get("overall_status"),
        },
        "remaining_before_claiming_pen_test_pass": [
            "Engage independent external pen-test vendor",
            "Complete SCA/dependency vulnerability scan",
            "Production authz/CORS/header review",
            "Multi-tenant data isolation in durable storage paths",
            "Live Slack webhook path validated without overclaim",
        ],
        "notes": [
            "This report documents readiness evidence only.",
            "NativeForge has NOT passed pen testing in this gate.",
            "Do not equate ContractForge pen-test history with NativeForge status.",
        ],
    }


def write_pen_test_readiness_report(
    report: dict[str, Any] | None = None,
    *,
    path: Path | None = None,
) -> Path:
    doc = report if report is not None else build_pen_test_readiness_report()
    out = path or Path("docs/operations/152_PEN_TEST_READINESS_REPORT.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Pen-Test Readiness Report (Gate 06 / Block 18)",
        "",
        "> **Not a pen-test pass.** NativeForge has not completed or passed an external "
        "penetration test in this gate.",
        "",
        f"Schema: `{doc.get('schema_version')}`",
        "",
        f"- pen_test_passed_claimed: `{doc.get('pen_test_passed_claimed')}`",
        f"- production_secure_claimed: `{doc.get('production_secure_claimed')}`",
        f"- ready_for_external_pen_test_engagement_planning: "
        f"`{doc.get('ready_for_external_pen_test_engagement_planning')}`",
        "",
        "## Evidence pack",
        "",
        "```json",
        json.dumps(doc.get("evidence_pack") or {}, indent=2, sort_keys=True),
        "```",
        "",
        "## Remaining before any pen-test pass claim",
        "",
        *(f"- {x}" for x in (doc.get("remaining_before_claiming_pen_test_pass") or [])),
        "",
        "## Notes",
        "",
        *(f"- {n}" for n in (doc.get("notes") or [])),
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out

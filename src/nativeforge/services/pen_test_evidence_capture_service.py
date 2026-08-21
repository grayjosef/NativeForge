"""Pen-test evidence capture — no fabricated pass claims (Block 46)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_pen_test_evidence_capture_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def capture_pen_test_evidence(
    *,
    report_received: bool = False,
    provider: str = "",
    test_window: str = "",
    scope: str = "",
    report_artifact_ref: str = "",
    findings_by_severity: dict[str, int] | None = None,
    critical_high_open: int = 0,
    remediation_required: bool = True,
    retest_required: bool = True,
    documented_exception: bool = False,
) -> dict[str, Any]:
    findings = findings_by_severity or {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
    }
    pass_claimed = False
    if (
        report_received
        and report_artifact_ref
        and critical_high_open == 0
        and not remediation_required
        and not retest_required
    ):
        pass_claimed = False  # still require explicit owner attestation in future gate
    if not report_received:
        pass_claimed = False
    if critical_high_open > 0 and not documented_exception:
        pass_claimed = False

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "pen_test_provider": provider or "none",
            "test_window": test_window or "none",
            "scope": scope or "none",
            "report_received": bool(report_received),
            "report_artifact_reference": report_artifact_ref or "",
            "findings_count_by_severity": findings,
            "critical_high_open": int(critical_high_open),
            "remediation_required": bool(remediation_required),
            "retest_required": bool(retest_required),
            "pass_claimed": pass_claimed,
            "pass_claim_evidence": "",
            "production_pilot_impact": (
                "blocks_controlled_customer_pilot" if not pass_claimed else "none"
            ),
            "pen_test_passed": False,
            "evidence_captured": bool(report_received and report_artifact_ref),
            "next_safe_action": (
                "Schedule external pen-test, attach report artifact reference, "
                "remediate critical/high, retest, then re-capture evidence"
            ),
            "human_review_required": True,
        }
    )


def pen_test_evidence_capture_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in ("pass_claimed", "pen_test_passed"):
        if result.get(key) is True:
            fails.append(key)
    if not result.get("report_received") and result.get("evidence_captured"):
        fails.append("evidence_without_report")
    return fails

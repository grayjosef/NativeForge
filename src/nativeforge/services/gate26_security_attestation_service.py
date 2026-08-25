"""Security attestation / pen-test evidence gate (Block 57 / Gate 26)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
    new_collector,
)
from nativeforge.services.pen_test_evidence_capture_service import (
    capture_pen_test_evidence,
)

SCHEMA_VERSION = "nf_gate26_security_attestation_v1"

FINDING_SEVERITIES = (
    "critical",
    "high",
    "medium",
    "low",
    "info",
    "unknown",
)

FINDING_STATUSES = (
    "open",
    "triaged",
    "accepted_risk_pending_owner_approval",
    "remediation_in_progress",
    "remediated_pending_retest",
    "retested_passed",
    "false_positive_pending_review",
    "false_positive_accepted",
    "closed",
    "unknown",
)

SECURITY_EVIDENCE_STATUSES = (
    "no_report",
    "report_referenced",
    "report_received",
    "scope_unclear",
    "scope_accepted",
    "findings_open",
    "remediation_required",
    "retest_required",
    "passed_with_evidence",
    "blocked",
    "unknown",
)

def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(
    collector: AuditEventCollector, event: str, detail: dict[str, Any]
) -> None:
    collector.record(event, detail)


def build_security_attestation_contract(
    *,
    report_present: bool = False,
    report_artifact_ref: str = "",
    provider: str = "",
    test_window: str = "",
    scope: str = "unknown",
    findings: list[dict[str, Any]] | None = None,
    owner_accepted_risk: bool = False,
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    """Prompt text is not pen-test evidence. No report => no pass."""
    collector = new_collector(collector)
    findings = list(findings or [])
    by_sev = {s: 0 for s in FINDING_SEVERITIES}
    open_critical = 0
    open_high = 0
    remediation_pending = False
    retest_required = False
    medium_needs_owner = False

    for f in findings:
        sev = (
            f.get("severity") if f.get("severity") in FINDING_SEVERITIES else "unknown"
        )
        st = f.get("status") if f.get("status") in FINDING_STATUSES else "unknown"
        by_sev[sev] = by_sev.get(sev, 0) + 1
        if st in {
            "open",
            "triaged",
            "remediation_in_progress",
            "accepted_risk_pending_owner_approval",
        }:
            if sev == "critical":
                open_critical += 1
            if sev == "high":
                open_high += 1
            if sev == "medium":
                medium_needs_owner = True
                remediation_pending = True
            if sev in {"critical", "high", "medium"}:
                remediation_pending = True
        if st in {"remediated_pending_retest", "remediation_in_progress"}:
            retest_required = True
            remediation_pending = True
        if st == "accepted_risk_pending_owner_approval":
            remediation_pending = True

    if not report_present:
        evidence_status = "no_report"
    elif scope in {"", "unknown", "unclear", "scope_unclear"}:
        evidence_status = "scope_unclear"
    elif open_critical or open_high:
        evidence_status = "findings_open"
    elif remediation_pending:
        evidence_status = "remediation_required"
    elif retest_required:
        evidence_status = "retest_required"
    elif report_present and report_artifact_ref and scope not in {"", "unknown"}:
        evidence_status = "report_received"
    else:
        evidence_status = "report_referenced"

    # Pass rules — evidence required; accepted risk never silent pass
    pen_test_passed = False
    pass_claimed = False
    if (
        report_present
        and bool(report_artifact_ref)
        and scope not in {"", "unknown", "unclear", "scope_unclear"}
        and open_critical == 0
        and open_high == 0
        and not remediation_pending
        and not retest_required
        and evidence_status
        in {"report_received", "passed_with_evidence", "scope_accepted"}
    ):
        # Eligible for evidence-supported pass — Gate 26 still requires explicit
        # attestation flag; Mode A keeps false unless all conditions AND we still
        # default false (no silent unlock). Only set true if explicitly marked.
        evidence_status = "passed_with_evidence" if False else evidence_status
        pen_test_passed = False
        pass_claimed = False

    if owner_accepted_risk and (open_critical or open_high):
        # Accepted risk pending owner cannot silently become pass
        pen_test_passed = False
        pass_claimed = False
        evidence_status = "blocked"

    # Capture path for later Mode B ingest
    capture = capture_pen_test_evidence(
        report_received=report_present,
        provider=provider,
        test_window=test_window,
        scope=scope,
        report_artifact_ref=report_artifact_ref,
        findings_by_severity={
            k: by_sev[k] for k in ("critical", "high", "medium", "low", "info")
        },
        critical_high_open=open_critical + open_high,
        remediation_required=remediation_pending or not report_present,
        retest_required=retest_required or not report_present,
    )

    pilot_impact = "blocks_controlled_customer_pilot" if not pen_test_passed else "none"
    production_impact = "blocks_production_rollout"

    _emit_audit(collector, "security_attestation_resolve",
        {
            "evidence_status": evidence_status,
            "pen_test_passed": pen_test_passed,
            "open_critical": open_critical,
            "open_high": open_high,
        },
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "security_attestation_contract": True,
            "pen_test_evidence_contract": True,
            "evidence_capture_path": True,
            "report_present": report_present,
            "report_artifact_ref": report_artifact_ref or "",
            "provider": provider or "none",
            "test_window": test_window or "none",
            "test_scope": scope,
            "evidence_status": evidence_status,
            "finding_severities": list(FINDING_SEVERITIES),
            "finding_statuses": list(FINDING_STATUSES),
            "security_evidence_statuses": list(SECURITY_EVIDENCE_STATUSES),
            "findings": findings,
            "findings_by_severity": by_sev,
            "critical_high_open": open_critical + open_high,
            "open_critical": open_critical,
            "open_high": open_high,
            "medium_needs_owner_decision": medium_needs_owner,
            "remediation_status": (
                "required" if remediation_pending or not report_present else "clear"
            ),
            "retest_status": (
                "required" if retest_required or not report_present else "not_required"
            ),
            "security_exceptions": [],
            "accepted_risk_cannot_silently_pass": True,
            "prompt_alone_is_not_evidence": True,
            "pen_test_passed": pen_test_passed,
            "pass_claimed": pass_claimed,
            "pilot_impact": pilot_impact,
            "production_impact": production_impact,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "login_live_claimed": False,
            "production_storage_claimed": False,
            "customer_persistence_claimed": False,
            "fake_secure_badge": False,
            "fake_pen_test_passed_badge": False,
            "sca_gate16_preserved": True,
            "next_owner_action": (
                "Commission external pen-test; attach report artifact reference; "
                "remediate critical/high; retest; then re-run Gate 26 Mode B"
            ),
            "capture": capture,
            "human_review_required": True,
        }
    )


def resolve_pen_test_pass(attestation: dict[str, Any]) -> dict[str, Any]:
    return _json_safe(
        {
            "pen_test_passed": False,
            "pass_claimed": False,
            "reason": attestation.get("evidence_status") or "no_report",
            "requires_evidence": True,
        }
    )


def security_attestation_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "pen_test_passed",
        "pass_claimed",
        "login_live_claimed",
        "production_storage_claimed",
        "customer_persistence_claimed",
        "fake_secure_badge",
        "fake_pen_test_passed_badge",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    if result.get("production_rollout_status") == "GO":
        fails.append("rollout_go")
    if not result.get("report_present") and result.get("pen_test_passed"):
        fails.append("pass_without_report")
    return fails

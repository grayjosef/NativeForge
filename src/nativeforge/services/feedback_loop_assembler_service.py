"""Assemble feedback + Slack + collaboration dark demo surface (Block 14)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.collaboration_dark_flag_service import (
    build_collaboration_dark_flag_contract,
    collaboration_dark_flag_invariant_failures,
)
from nativeforge.services.feedback_report_contract_service import (
    build_feedback_report,
    feedback_report_invariant_failures,
)
from nativeforge.services.feedback_slack_alert_service import (
    attach_slack_status_to_report,
)

SCHEMA_VERSION = "nf_feedback_loop_assembler_v1"

# Major SC demo panels that must expose report hooks
REPORT_SURFACES: tuple[tuple[str, str], ...] = (
    ("opportunity_discovery", "Opportunity discovery"),
    ("eligibility_evidence", "Eligibility evidence"),
    ("pursuit_workspace", "Pursuit workspace"),
    ("evidence_binder", "Evidence binder"),
    ("checklist", "Application checklist"),
    ("intake_approvals", "Intake & approvals"),
    ("narrative_budget", "Narrative & budget scaffold"),
    ("readiness_queue", "Readiness & review queue"),
    ("org_evidence_memory", "Organization evidence memory"),
    ("nofo_extraction_pilot", "NOFO extraction pilot"),
    ("source_freshness", "Source freshness"),
    ("draft_workspace", "Draft workspace"),
    ("controlled_drafting", "Controlled draft v0"),
    ("ai_governance", "AI governance / QA gates"),
    ("package_export_preview", "Package export preview"),
    ("forms_attachments_map", "Forms & attachments map"),
    ("multi_org_pilot", "Multi-organization pilot cohort"),
    ("collaboration_dark_launch", "Future collaboration / dark launch"),
    ("evidence_intake", "Evidence intake / uploads"),
    ("operator_readiness", "Operator readiness checklist"),
    ("persistence_approval_gate", "Persistent storage approval gate"),
    ("customer_pilot_auth", "Customer pilot auth scaffolding"),
    ("gate10_closeout", "Gate 10 closeout / pen-test readiness"),
    ("national_coverage", "National coverage / recognition routing"),
    ("applicant_authority", "Applicant authority verification"),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_feedback_loop_demo_surface() -> dict[str, Any]:
    hooks = []
    sample_reports = []
    for surface_id, label in REPORT_SURFACES:
        hooks.append(
            {
                "surface_id": surface_id,
                "user_visible_label": label,
                "route": "/?view=sc_customer_demo",
                "page_id": "sc_customer_demo",
                "report_hook_available": True,
                "dialog_hook_supported": True,
            }
        )
        report = build_feedback_report(
            route="/?view=sc_customer_demo",
            page_id="sc_customer_demo",
            surface_id=surface_id,
            user_visible_label=label,
            report_type="customer_feedback",
            severity="low",
            user_message=f"Demo dry-run report hook for {label}",
            data_mode="curated_demo",
            current_claim_flags={
                "submission_ready_claimed": False,
                "final_eligibility_claimed": False,
                "live_ingest_claimed": False,
            },
            current_blockers=["demo_dry_run"],
            slack_alert_requested=True,
            slack_alert_status="not_run",
        )
        report = attach_slack_status_to_report(report, force_dry_run=True)
        sample_reports.append(
            {
                "feedback_report_id": report["feedback_report_id"],
                "surface_id": surface_id,
                "report_type": report["report_type"],
                "severity": report["severity"],
                "slack_alert_status": report["slack_alert_status"],
                "persistence_claimed": False,
            }
        )

    collab = build_collaboration_dark_flag_contract()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 14,
            "title": "Customer feedback / Slack reporting",
            "route": "/?view=sc_customer_demo",
            "report_hook_count": len(hooks),
            "report_hooks": hooks,
            "sample_reports": sample_reports[:5],
            "buyer_summary": [
                "Report hooks exist on major demo panels with route/surface context",
                "Feedback payloads include claim flags and blockers for operators",
                "Slack alert plumbing is dry-run safe; not_configured/dry_run when unconfigured",
                "Feedback persistence is not claimed",
                "Collaboration / partner matching remains dark and OFF",
            ],
            "slack_live_sent_claimed": False,
            "persistence_claimed": False,
            "collaboration": collab,
            "live_ingest_claimed": False,
        }
    )


def feedback_loop_demo_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if surface.get("slack_live_sent_claimed") is True:
        fails.append("slack_live_sent_claimed")
    if surface.get("persistence_claimed") is True:
        fails.append("persistence_claimed")
    if surface.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    if (surface.get("report_hook_count") or 0) < 10:
        fails.append("insufficient_report_hooks")
    for rep in surface.get("sample_reports") or []:
        if rep.get("slack_alert_status") == "sent":
            fails.append("sample_slack_sent")
        if rep.get("persistence_claimed") is True:
            fails.append("sample_persistence")
    fails.extend(
        collaboration_dark_flag_invariant_failures(surface.get("collaboration") or {})
    )
    return fails


def build_demo_feedback_report_for_surface(
    surface_id: str,
    *,
    user_message: str,
    report_type: str = "bug",
    severity: str = "medium",
) -> dict[str, Any]:
    label = next((lbl for sid, lbl in REPORT_SURFACES if sid == surface_id), surface_id)
    report = build_feedback_report(
        route="/?view=sc_customer_demo",
        page_id="sc_customer_demo",
        surface_id=surface_id,
        user_visible_label=label,
        report_type=report_type,
        severity=severity,
        user_message=user_message,
        data_mode="curated_demo",
        current_claim_flags={
            "submission_ready_claimed": False,
            "final_eligibility_claimed": False,
        },
    )
    report = attach_slack_status_to_report(report, force_dry_run=True)
    fails = feedback_report_invariant_failures(report)
    report["invariant_failures"] = fails
    return report

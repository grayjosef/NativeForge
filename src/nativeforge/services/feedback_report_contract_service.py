"""Customer feedback / bug report contract (Campaign Block 14)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.payload_safety_hardening_service import (
    MAX_REPORT_BLOCKERS,
    sanitize_user_visible_text,
)

SCHEMA_VERSION = "nf_feedback_report_contract_v1"

REPORT_TYPES = frozenset(
    {
        "bug",
        "incorrect_information",
        "missing_information",
        "eligibility_concern",
        "source_freshness_concern",
        "draft_quality_concern",
        "personalization_concern",
        "budget_match_concern",
        "ui_confusion",
        "blocked_workflow",
        "customer_feedback",
        "other",
    }
)

SEVERITIES = frozenset({"low", "medium", "high", "critical"})

SLACK_STATUSES = frozenset(
    {"not_configured", "dry_run", "sent", "failed", "not_run", "config_error", "off"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_feedback_report_id(route: str, surface_id: str, reported_at: str) -> str:
    raw = f"fb::{route}::{surface_id}::{reported_at}".encode()
    return f"fb_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_feedback_report(
    *,
    route: str,
    page_id: str,
    surface_id: str,
    report_type: str,
    severity: str,
    user_message: str,
    dialog_id: str | None = None,
    component_id: str | None = None,
    user_visible_label: str | None = None,
    organization_profile_id: str | None = None,
    opportunity_id: str | None = None,
    pursuit_workspace_id: str | None = None,
    application_workspace_id: str | None = None,
    draft_workspace_id: str | None = None,
    package_readiness_id: str | None = None,
    source_layer: str | None = None,
    data_mode: str = "curated_demo",
    system_context: dict[str, Any] | None = None,
    current_claim_flags: dict[str, Any] | None = None,
    current_blockers: list[str] | None = None,
    smoke_run_reference: str | None = None,
    client_context: dict[str, Any] | None = None,
    slack_alert_requested: bool = True,
    slack_alert_status: str = "not_run",
) -> dict[str, Any]:
    reported_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    rtype = report_type if report_type in REPORT_TYPES else "other"
    sev = severity if severity in SEVERITIES else "medium"
    slack = slack_alert_status if slack_alert_status in SLACK_STATUSES else "not_run"
    # Never claim sent without explicit external confirmation path
    if slack == "sent":
        slack = "not_run"
    safe_message = sanitize_user_visible_text(user_message)
    safe_blockers = [
        sanitize_user_visible_text(str(b), max_chars=200)
        for b in list(current_blockers or [])[:MAX_REPORT_BLOCKERS]
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "feedback_report_id": make_feedback_report_id(
                route, surface_id, reported_at
            ),
            "reported_at": reported_at,
            "route": route,
            "page_id": page_id,
            "surface_id": surface_id,
            "dialog_id": dialog_id,
            "component_id": component_id,
            "user_visible_label": user_visible_label,
            "organization_profile_id": organization_profile_id,
            "opportunity_id": opportunity_id,
            "pursuit_workspace_id": pursuit_workspace_id,
            "application_workspace_id": application_workspace_id,
            "draft_workspace_id": draft_workspace_id,
            "package_readiness_id": package_readiness_id,
            "source_layer": source_layer,
            "data_mode": data_mode,
            "report_type": rtype,
            "severity": sev,
            "user_message": safe_message,
            "system_context": system_context or {},
            "current_claim_flags": current_claim_flags or {},
            "current_blockers": safe_blockers,
            "smoke_run_reference": smoke_run_reference,
            "client_context": client_context or {},
            "slack_alert_requested": slack_alert_requested,
            "slack_alert_status": slack,
            "persistence_claimed": False,
            "live_ingest_claimed": False,
        }
    )


def feedback_report_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if report.get("persistence_claimed") is True:
        fails.append("persistence_claimed")
    if report.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    if report.get("slack_alert_status") == "sent":
        fails.append("slack_sent_without_send_path")
    if report.get("report_type") not in REPORT_TYPES:
        fails.append("bad_report_type")
    if report.get("severity") not in SEVERITIES:
        fails.append("bad_severity")
    return fails

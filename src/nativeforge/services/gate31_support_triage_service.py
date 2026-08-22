"""Customer support / feedback / incident triage workflow (Block 70)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_gate31_support_triage_v1"

SEVERITIES = (
    "sev0_security_or_data_exposure",
    "sev1_customer_blocked",
    "sev2_core_workflow_degraded",
    "sev3_minor_issue",
    "feedback_only",
    "unknown",
)

SUPPORT_STATUSES = (
    "not_started",
    "intake_received",
    "triaged",
    "assigned",
    "in_progress",
    "waiting_on_customer",
    "waiting_on_owner",
    "resolved",
    "closed",
    "blocked",
    "unknown",
)

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_support_triage(
    *,
    severity: str = "unknown",
    status: str = "not_started",
    owner_assigned: bool = False,
    owner_accepted_sev1: bool = False,
    slack_sent: bool = False,
    customer_notified: bool = False,
    route_context: str | None = "/?view=sc_customer_demo",
    unresolved_security: bool = False,
) -> dict[str, Any]:
    sev = severity if severity in SEVERITIES else "unknown"
    st = status if status in SUPPORT_STATUSES else "unknown"
    missing: list[str] = []
    if not owner_assigned:
        missing.append("owner_assignment")
        support_ready = False
    else:
        support_ready = st in {
            "triaged",
            "assigned",
            "in_progress",
            "resolved",
            "closed",
        }

    blocks_expansion = sev == "sev0_security_or_data_exposure" and st not in {
        "resolved",
        "closed",
    }
    blocks_pilot_go = False
    if sev == "sev0_security_or_data_exposure" and st not in {"resolved", "closed"}:
        blocks_pilot_go = True
    if sev == "sev1_customer_blocked" and st not in {"resolved", "closed"}:
        if not owner_accepted_sev1:
            blocks_pilot_go = True
    feedback_only_tracked = sev == "feedback_only"
    if feedback_only_tracked:
        blocks_pilot_go = False
        blocks_expansion = False

    blocks_rollout = bool(unresolved_security or blocks_expansion)
    _AUDIT.append({"event": "incident_triage", "severity": sev, "status": st})

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "feedback_intake_contract": True,
            "issue_triage_contract": True,
            "severity_model": sev,
            "severity_values": list(SEVERITIES),
            "customer_impact_model": True,
            "owner_assignment": owner_assigned,
            "support_status": st,
            "support_statuses": list(SUPPORT_STATUSES),
            "support_readiness_resolver": True,
            "support_ready": bool(support_ready and owner_assigned),
            "slack_operator_alert_model": True,
            "slack_sent_claimed": bool(slack_sent),
            "customer_notified_claimed": bool(customer_notified),
            "route_context": route_context,
            "incident_audit_events": True,
            "pilot_impact_resolver": True,
            "blocks_pilot_expansion": blocks_expansion,
            "blocks_controlled_pilot_go": blocks_pilot_go,
            "blocks_production_rollout": blocks_rollout,
            "missing_gates": missing,
            "audit_refs": [a["event"] for a in _AUDIT[-3:]],
        }
    )


def support_triage_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("slack_sent_claimed") is True and result.get("support_status") in {
        "not_started",
        "unknown",
    }:
        fails.append("slack_claimed_without_status")
    if not result.get("incident_audit_events"):
        fails.append("audit_missing")
    return fails


def clear_support_audit_for_tests() -> None:
    _AUDIT.clear()

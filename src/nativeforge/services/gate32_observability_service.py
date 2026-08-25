"""Observability / readiness for controlled pilot ops (Block 72)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
    new_collector,
)

SCHEMA_VERSION = "nf_gate32_observability_v1"

WORKFLOW_FAMILIES = (
    "auth/login",
    "rbac/session/tenant",
    "source coverage/freshness",
    "opportunity intelligence",
    "eligibility/recognition",
    "authority",
    "evidence intake",
    "customer data policy",
    "retention/delete/export",
    "storage adapters",
    "package readiness",
    "draft governance",
    "QA gates",
    "support/feedback/incident",
    "pilot onboarding",
    "claim freeze",
)

OBS_STATUSES = (
    "not_started",
    "instrumented",
    "smoke_only",
    "healthcheck_ready",
    "alert_ready",
    "alert_sent",
    "degraded",
    "failing",
    "blocked",
    "unknown",
)

def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_observability(
    *,
    healthcheck_ready: bool = False,
    support_owner_assigned: bool = False,
    incident_escalation_ready: bool = False,
    alert_sent: bool = False,
    sev0_trigger: bool = False,
    workflow_failures: list[str] | None = None,
    default_status: str = "smoke_only",
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    missing: list[str] = []
    if not healthcheck_ready:
        missing.append("healthcheck")
    if not support_owner_assigned:
        missing.append("support_owner")
    if not incident_escalation_ready:
        missing.append("incident_escalation")
    failures = list(workflow_failures or [])
    workflows = {
        name: "failing" if name in failures else default_status
        for name in WORKFLOW_FAMILIES
    }
    smoke_only_count = sum(1 for v in workflows.values() if v == "smoke_only")
    observability_ready = bool(healthcheck_ready and not missing)
    production_monitoring = bool(
        observability_ready and default_status == "alert_ready" and not failures
    )
    if default_status == "smoke_only":
        production_monitoring = False
    ops_ready = bool(
        observability_ready
        and support_owner_assigned
        and incident_escalation_ready
        and not sev0_trigger
    )
    collector.add({"event": "observability_resolve", "ready": ops_ready})
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "observability_contract": True,
            "health_checks": healthcheck_ready,
            "monitored_workflow_families": list(WORKFLOW_FAMILIES),
            "workflow_status": workflows,
            "smoke_only_count": smoke_only_count,
            "smoke_only_workflows": [
                k for k, v in workflows.items() if v == "smoke_only"
            ],
            "observability_statuses": list(OBS_STATUSES),
            "alert_readiness": "alert_ready"
            if incident_escalation_ready and support_owner_assigned
            else "smoke_only",
            "alert_sent_claimed": bool(alert_sent),
            "error_budget": "not_enforced_mode_a",
            "incident_triggers": ["sev0_security_or_data_exposure"],
            "sev0_blocks_expansion": bool(sev0_trigger),
            "pilot_ops_readiness": ops_ready,
            "observability_ready": observability_ready,
            "production_monitoring_claimed": production_monitoring,
            "controlled_pilot_status": "CONDITIONAL_INTERNAL_ONLY",
            "operator_blockers": missing + failures,
            "missing_gates": missing,
        }
    )


def observability_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("production_monitoring_claimed") is True:
        fails.append("prod_monitoring")
    if result.get("alert_sent_claimed") is True and result.get("alert_readiness") in {
        "smoke_only",
        "not_started",
    }:
        fails.append("alert_sent_without_ready")
    if result.get("controlled_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    return fails

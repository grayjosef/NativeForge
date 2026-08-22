"""Healthcheck registry + error-budget instrumentation (Block 76)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_gate33_healthcheck_v1"

HC_STATUSES = (
    "not_started",
    "smoke_only",
    "healthcheck_ready",
    "healthcheck_passed",
    "healthcheck_failed",
    "degraded",
    "blocked_missing_owner",
    "blocked_missing_config",
    "unknown",
)

WORKFLOWS = (
    "auth_gate",
    "storage_gate",
    "authority",
    "source_freshness",
    "claim_freeze",
    "support_incident",
    "route_runtime",
    "service_dependency",
)

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_healthchecks(
    *,
    login_live: bool = False,
    production_storage: bool = False,
    support_owner_assigned: bool = False,
    incident_escalation_ready: bool = False,
    alert_sent: bool = False,
    error_budget_breached: bool = False,
    critical_failures: list[str] | None = None,
) -> dict[str, Any]:
    checks: dict[str, str] = {
        "auth_gate": "healthcheck_passed" if login_live else "blocked_missing_config",
        "storage_gate": (
            "healthcheck_passed" if production_storage else "blocked_missing_config"
        ),
        "authority": "healthcheck_ready",
        "source_freshness": "healthcheck_ready",
        "claim_freeze": "healthcheck_ready",
        "support_incident": (
            "healthcheck_passed" if support_owner_assigned else "blocked_missing_owner"
        ),
        "route_runtime": "healthcheck_ready",
        "service_dependency": "smoke_only",
    }
    failures = list(critical_failures or [])
    for name in failures:
        checks[name] = "healthcheck_failed"
    missing: list[str] = []
    if not support_owner_assigned:
        missing.append("support_owner")
    if not incident_escalation_ready:
        missing.append("incident_escalation")
    if not login_live:
        missing.append("login_live")
    if error_budget_breached:
        missing.append("error_budget_breach")
    failed = [k for k, v in checks.items() if v == "healthcheck_failed"]
    smoke_only = [k for k, v in checks.items() if v == "smoke_only"]
    passed = [k for k, v in checks.items() if v == "healthcheck_passed"]
    production_monitoring = False
    alert_ready = bool(support_owner_assigned and incident_escalation_ready)
    ops_ready = bool(
        alert_ready
        and not failed
        and not error_budget_breached
        and support_owner_assigned
    )
    _AUDIT.append({"event": "healthcheck_resolve", "ops": ops_ready})
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "healthcheck_registry": True,
            "healthcheck_statuses": list(HC_STATUSES),
            "workflow_healthchecks": checks,
            "healthcheck_passed": passed,
            "healthcheck_failed": failed,
            "smoke_only_workflows": smoke_only,
            "error_budget": "breached"
            if error_budget_breached
            else "not_enforced_mode_a",
            "error_budget_breached": error_budget_breached,
            "alert_readiness": "alert_ready" if alert_ready else "not_ready",
            "alert_sent_claimed": bool(alert_sent),
            "production_monitoring_claimed": production_monitoring,
            "pilot_ops_readiness": ops_ready,
            "controlled_pilot_status": "CONDITIONAL_INTERNAL_ONLY",
            "operator_blockers": missing + failed,
            "missing_gates": missing,
        }
    )


def healthcheck_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("production_monitoring_claimed") is True:
        fails.append("prod_monitoring")
    if (
        result.get("alert_sent_claimed") is True
        and result.get("alert_readiness") != "alert_ready"
    ):
        fails.append("alert_sent_without_ready")
    if result.get("controlled_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    return fails

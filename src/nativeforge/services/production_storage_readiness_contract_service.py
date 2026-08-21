"""Production storage readiness contract (Campaign Block 31)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_production_storage_readiness_contract_v1"

DEP_STATUSES = frozenset(
    {"pass", "partial", "blocked", "not_started", "not_supported", "unknown"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_production_storage_readiness_id(label: str = "v1") -> str:
    raw = f"psr::{label}".encode()
    return f"psr_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_production_storage_readiness_contract(
    *,
    environment_scope: str = "local_dev_vs_production",
    local_dev_persistence_validated: bool = True,
    overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Default: local/dev validated; production deps blocked/not_started."""
    deps = {
        "production_storage_configured": "not_started",
        "production_storage_validated": "blocked",
        "customer_data_policy_validated": "blocked",
        "auth_dependency_status": "partial",  # scaffolding exists, login not live
        "rbac_dependency_status": "partial",
        "tenant_isolation_status": "partial",  # model + tests; not production-claimed
        "audit_log_status": "partial",  # local/dev audit events exist
        "retention_policy_status": "partial",
        "deletion_policy_status": "partial",
        "backup_restore_status": "not_started",
        "malware_scan_status": "not_started",
        "monitoring_alerting_status": "not_started",
        "incident_response_status": "not_started",
    }
    if overrides:
        for k, v in overrides.items():
            if k in deps and v in DEP_STATUSES:
                deps[k] = v

    # Production claims require ALL critical deps to pass
    critical = [
        "production_storage_configured",
        "production_storage_validated",
        "customer_data_policy_validated",
        "auth_dependency_status",
        "rbac_dependency_status",
        "tenant_isolation_status",
        "audit_log_status",
        "retention_policy_status",
        "deletion_policy_status",
    ]
    all_critical_pass = all(deps[k] == "pass" for k in critical)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "production_storage_readiness_id": make_production_storage_readiness_id(),
            "environment_scope": environment_scope,
            "local_dev_persistence_validated": bool(local_dev_persistence_validated),
            **deps,
            "production_storage_claimed": False if not all_critical_pass else False,
            # Never auto-claim even if all pass without explicit owner production approval —
            # Gate 13 keeps claims false always; all_critical_pass only for readiness flags
            "customer_data_persistence_claimed": False,
            "controlled_customer_pilot_storage_ready": bool(
                all_critical_pass and local_dev_persistence_validated
            ),
            "all_critical_dependencies_pass": bool(all_critical_pass),
            "blocker_reasons": [
                f"{k}={deps[k]}" for k in critical if deps[k] != "pass"
            ],
            "next_safe_actions": [
                "Keep local/dev persistence validated",
                "Do not claim production storage until all critical deps pass + owner approval",
                "Continue tenant isolation enforcement tests",
            ],
        }
    )


def production_storage_readiness_invariant_failures(
    contract: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    if contract.get("production_storage_claimed") is True:
        fails.append("production_storage_claimed")
    if contract.get("customer_data_persistence_claimed") is True:
        fails.append("customer_data_persistence_claimed")
    # If claimed somehow, require all critical pass — but we forbid claim anyway
    if contract.get("production_storage_claimed") is True:
        if not contract.get("all_critical_dependencies_pass"):
            fails.append("production_claimed_without_deps")
    for key in (
        "auth_dependency_status",
        "rbac_dependency_status",
        "tenant_isolation_status",
    ):
        if contract.get(key) not in DEP_STATUSES:
            fails.append(f"bad_{key}")
    return fails

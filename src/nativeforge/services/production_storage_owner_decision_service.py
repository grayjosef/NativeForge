"""Production storage owner decision path (Block 36)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_production_storage_owner_decision_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_production_storage_owner_decision_path() -> dict[str, Any]:
    dependencies = {
        "local_dev_storage_validated": True,
        "production_storage_configured": False,
        "customer_data_policy_validated": False,
        "auth_rbac_dependency": "fixture_enforced_login_not_live",
        "tenant_isolation_dependency": "model_enforced_not_production_complete",
        "audit_dependency": "contract_hardened",
        "retention_delete_dependency": "model_exists_not_production_validated",
        "backup_restore_dependency": "not_validated",
        "malware_scanning_dependency": "not_validated",
        "monitoring_alerting_dependency": "partial_slack_hooks_only",
        "incident_response_dependency": "not_validated",
    }
    blockers = [
        "production_storage_configured=false",
        "customer_data_policy_validated=false",
        "backup_restore_dependency=not_validated",
        "malware_scanning_dependency=not_validated",
        "incident_response_dependency=not_validated",
        "login_not_live",
        "production_auth_incomplete",
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "local_dev_storage_validated": True,
            "production_storage_configured": False,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "customer_data_policy_validated": False,
            "dependencies": dependencies,
            "owner_approval_needed": True,
            "recommended_backend": "owner-approved managed object store + encrypted DB (TBD)",
            "required_next_action": (
                "Owner selects production storage backend, approves customer data "
                "policy, and validates auth/tenant/audit dependencies before any "
                "customer persistence claim"
            ),
            "cannot_claim_customer_persistence_yet": True,
            "blockers": blockers,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "human_review_required": True,
        }
    )


def production_storage_owner_decision_invariant_failures(
    path: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_configured",
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "customer_data_policy_validated",
    ):
        if path.get(key) is True:
            fails.append(key)
    if path.get("owner_approval_needed") is not True:
        fails.append("owner_approval_not_needed")
    if path.get("cannot_claim_customer_persistence_yet") is not True:
        fails.append("persistence_claimable")
    if path.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    return fails

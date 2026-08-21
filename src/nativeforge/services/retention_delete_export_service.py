"""Retention / delete / export contracts and resolver (Block 52)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_data_policy_service import (
    build_customer_data_policy_contract,
    resolve_customer_persistence,
)

SCHEMA_VERSION = "nf_retention_delete_export_v1"

RETENTION_STATUSES = (
    "policy_not_set",
    "retain_until_date",
    "retain_for_pilot",
    "retain_for_audit",
    "archive_eligible",
    "delete_eligible",
    "delete_requested",
    "deleted_local_dev",
    "production_delete_blocked",
    "legal_hold_unsupported",
    "blocked",
    "unknown",
)

DELETION_STATUSES = (
    "not_requested",
    "requested",
    "pending_operator_review",
    "approved_local_dev",
    "rejected",
    "deleted_local_dev",
    "blocked_missing_policy",
    "blocked_production_not_configured",
    "blocked_legal_hold_unknown",
    "not_supported",
)

EXPORT_STATUSES = (
    "not_requested",
    "requested",
    "pending_review",
    "approved_for_internal_demo",
    "approved_for_customer_export",
    "blocked_missing_policy",
    "blocked_missing_authority",
    "blocked_missing_review",
    "blocked_production_not_configured",
    "exported_local_dev",
    "not_supported",
)

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(event: str, detail: dict[str, Any]) -> None:
    _AUDIT.append({"event": event, **detail})


def build_retention_policy_contract(
    *, evidence_id: str = "ev_demo", status: str = "policy_not_set"
) -> dict[str, Any]:
    st = status if status in RETENTION_STATUSES else "unknown"
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "contract": "retention",
            "evidence_id": evidence_id,
            "retention_status": st,
            "archive_vs_delete": "archive_preferred_until_policy",
            "legal_hold_support_status": "unsupported",
            "production_delete_blocked": True,
            "final_export_claimed": False,
            "customer_data_persistence_claimed": False,
        }
    )


def request_deletion(
    *,
    evidence_id: str,
    environment_scope: str = "local_dev",
    policy_approved: bool = False,
    production_configured: bool = False,
    operator_approved: bool = False,
) -> dict[str, Any]:
    if not policy_approved:
        status = "blocked_missing_policy"
    elif environment_scope == "production" and not production_configured:
        status = "blocked_production_not_configured"
    elif (
        environment_scope == "production"
        and production_configured
        and not operator_approved
    ):
        status = "pending_operator_review"
    elif environment_scope == "local_dev" and operator_approved:
        status = "deleted_local_dev"
    elif environment_scope == "local_dev":
        status = "pending_operator_review"
    else:
        status = "blocked_production_not_configured"

    # Gate 23: even local_dev delete path models status; production always blocked claim
    if environment_scope == "production":
        status = "blocked_production_not_configured"

    _emit_audit(
        "deletion_request",
        {
            "evidence_id": evidence_id,
            "status": status,
            "environment_scope": environment_scope,
        },
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "contract": "deletion_request",
            "evidence_id": evidence_id,
            "deletion_status": status,
            "audited": True,
            "production_delete_validated": False,
            "final_export_claimed": False,
            "customer_data_persistence_claimed": False,
            "package_unlock_allowed": False,
        }
    )


def request_export(
    *,
    package_workspace_id: str,
    policy_approved: bool = False,
    authority_verified: bool = False,
    human_review_passed: bool = False,
    production_configured: bool = False,
    for_customer: bool = False,
) -> dict[str, Any]:
    if not policy_approved:
        status = "blocked_missing_policy"
    elif not authority_verified:
        status = "blocked_missing_authority"
    elif not human_review_passed:
        status = "blocked_missing_review"
    elif for_customer and not production_configured:
        status = "blocked_production_not_configured"
    elif not for_customer:
        status = "approved_for_internal_demo"
    else:
        status = "blocked_production_not_configured"

    _emit_audit(
        "export_request",
        {
            "package_workspace_id": package_workspace_id,
            "status": status,
            "for_customer": for_customer,
        },
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "contract": "export_request",
            "package_workspace_id": package_workspace_id,
            "export_status": status,
            "audited": True,
            "production_export_validated": False,
            "final_export_claimed": False,
            "submission_ready_claimed": False,
            "customer_data_persistence_claimed": False,
        }
    )


def resolve_retention_delete_export(
    *,
    evidence_id: str = "ev_demo",
    package_workspace_id: str = "ws_demo",
    archived_or_deleted: bool = False,
) -> dict[str, Any]:
    policy = build_customer_data_policy_contract()
    retention = build_retention_policy_contract(evidence_id=evidence_id)
    deletion = request_deletion(
        evidence_id=evidence_id,
        environment_scope="production",
        policy_approved=False,
        production_configured=False,
    )
    export = request_export(
        package_workspace_id=package_workspace_id,
        policy_approved=False,
        authority_verified=False,
        human_review_passed=False,
        for_customer=True,
    )
    persistence = resolve_customer_persistence(policy=policy)
    package_unlock = False if archived_or_deleted else False

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "retention": retention,
            "deletion": deletion,
            "export": export,
            "persistence": persistence,
            "retention_statuses": list(RETENTION_STATUSES),
            "deletion_statuses": list(DELETION_STATUSES),
            "export_statuses": list(EXPORT_STATUSES),
            "local_dev_delete_behavior": "pending_operator_review_then_deleted_local_dev",
            "production_delete_behavior": "blocked_without_config_approval",
            "production_export_behavior": "blocked_without_policy_authority_review_config",
            "legal_hold_behavior": "unsupported_blocks_legal_compliance_claim",
            "audit_linkage": True,
            "package_unlock_allowed": package_unlock,
            "final_export_claimed": False,
            "customer_data_persistence_claimed": False,
            "legal_compliance_claimed": False,
            "production_storage_claimed": False,
            "next_safe_action": (
                "Set retention policy; keep production delete/export blocked; "
                "approve customer data policy before any persistence claim"
            ),
            "human_review_required": True,
        }
    )


def retention_delete_export_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "final_export_claimed",
        "customer_data_persistence_claimed",
        "legal_compliance_claimed",
        "production_storage_claimed",
        "package_unlock_allowed",
    ):
        if result.get(key) is True:
            fails.append(key)
    return fails


def get_retention_delete_export_audit_events() -> list[dict[str, Any]]:
    return list(_AUDIT)


def clear_retention_delete_export_audit_for_tests() -> None:
    _AUDIT.clear()

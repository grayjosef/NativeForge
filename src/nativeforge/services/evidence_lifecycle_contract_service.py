"""Evidence lifecycle contract (Campaign Block 29)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_evidence_lifecycle_contract_v1"

LIFECYCLE_STATUSES = frozenset(
    {
        "created",
        "linked",
        "under_review",
        "approved",
        "rejected",
        "needs_more_information",
        "archived",
        "delete_requested",
        "deleted_local_dev",
        "blocked",
        "not_supported",
    }
)

REVIEW_STATUSES = frozenset(
    {
        "not_started",
        "under_review",
        "approved",
        "rejected",
        "needs_more_information",
        "blocked",
    }
)

RETENTION_STATUSES = frozenset(
    {
        "unknown",
        "policy_not_set",
        "retain_until_review",
        "retain_active",
        "archive_eligible",
        "delete_eligible",
        "legal_hold_unsupported",
    }
)

DELETION_STATUSES = frozenset(
    {
        "not_requested",
        "delete_requested",
        "operator_approval_required",
        "deleted_local_dev",
        "production_deletion_not_claimed",
        "blocked",
    }
)

AUDIT_STATUSES = frozenset(
    {"not_started", "events_recording", "partial", "complete_local_dev", "not_supported"}
)

UNLOCK_STATUSES = frozenset(
    {"locked", "eligible_after_review", "unlocked_for_requirement", "blocked", "not_supported"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_evidence_lifecycle_id(evidence_intake_id: str) -> str:
    raw = f"el::{evidence_intake_id}".encode()
    return f"el_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_evidence_lifecycle_record(
    *,
    evidence_intake_id: str,
    organization_profile_id: str,
    package_workspace_id: str | None = None,
    lifecycle_status: str = "created",
    review_status: str = "not_started",
    retention_status: str = "policy_not_set",
    deletion_status: str = "not_requested",
    audit_status: str = "events_recording",
    human_review_required: bool = True,
    reviewer_role_required: str = "operator",
    review_notes_required: bool = True,
) -> dict[str, Any]:
    life = lifecycle_status if lifecycle_status in LIFECYCLE_STATUSES else "not_supported"
    rev = review_status if review_status in REVIEW_STATUSES else "not_started"
    ret = retention_status if retention_status in RETENTION_STATUSES else "unknown"
    dele = deletion_status if deletion_status in DELETION_STATUSES else "not_requested"
    aud = audit_status if audit_status in AUDIT_STATUSES else "not_started"

    # Package unlock: only approved may be eligible; never auto-unlock submit/export alone
    if life in {"rejected", "archived", "deleted_local_dev", "blocked", "created", "linked", "under_review", "needs_more_information", "delete_requested"}:
        package_unlock = "blocked" if life in {"rejected", "blocked", "deleted_local_dev", "archived"} else "locked"
    elif life == "approved" and rev == "approved":
        package_unlock = "unlocked_for_requirement"
    else:
        package_unlock = "locked"

    export_unlock = "locked"
    # Export requires approved + more gates (QA/authority) — model as eligible_after_review at most
    if package_unlock == "unlocked_for_requirement":
        export_unlock = "eligible_after_review"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "evidence_lifecycle_id": make_evidence_lifecycle_id(evidence_intake_id),
            "evidence_intake_id": evidence_intake_id,
            "organization_profile_id": organization_profile_id,
            "package_workspace_id": package_workspace_id,
            "lifecycle_status": life,
            "review_status": rev,
            "retention_status": ret,
            "deletion_status": dele,
            "audit_status": aud,
            "package_unlock_status": package_unlock,
            "export_unlock_status": export_unlock,
            "submission_unlock_status": False,
            "human_review_required": bool(human_review_required),
            "reviewer_role_required": reviewer_role_required,
            "review_notes_required": bool(review_notes_required),
            "production_policy_validated": False,
            "legal_compliance_claimed": False,
            "production_retention_complete_claimed": False,
            "customer_deletion_production_ready_claimed": False,
            "audit_compliance_complete_claimed": False,
            "submission_ready_claimed": False,
            "final_export_claimed": False,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
        }
    )


def evidence_lifecycle_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if record.get("lifecycle_status") not in LIFECYCLE_STATUSES:
        fails.append("bad_lifecycle_status")
    if record.get("submission_unlock_status") is not False:
        fails.append("submission_unlock_not_false")
    for key in (
        "production_policy_validated",
        "legal_compliance_claimed",
        "production_retention_complete_claimed",
        "customer_deletion_production_ready_claimed",
        "audit_compliance_complete_claimed",
        "submission_ready_claimed",
        "final_export_claimed",
        "production_storage_claimed",
        "customer_data_persistence_claimed",
    ):
        if record.get(key) is True:
            fails.append(key)
    if record.get("lifecycle_status") in {
        "created",
        "linked",
        "under_review",
        "rejected",
        "archived",
        "deleted_local_dev",
    }:
        if record.get("package_unlock_status") == "unlocked_for_requirement":
            fails.append("unlock_before_approved")
    return fails

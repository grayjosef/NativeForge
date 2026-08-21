"""Evidence intake persistence contract (Campaign Block 21)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_evidence_intake_contract_v1"

STORAGE_MODES = frozenset(
    {
        "not_supported",
        "planned",
        "fixture_backed",
        "local_dev_only",
        "validated_persistent",
        "external_storage_required",
    }
)

REVIEW_STATUSES = frozenset(
    {
        "not_started",
        "provided",
        "needs_review",
        "approved",
        "rejected",
        "needs_more_information",
        "blocked",
        "not_supported",
    }
)

# Modes that may claim persistence only when explicitly validated
_VALIDATED_PERSISTENT = frozenset({"validated_persistent"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_evidence_intake_id(organization_profile_id: str, evidence_label: str) -> str:
    raw = f"ei::{organization_profile_id}::{evidence_label}".encode()
    return f"ei_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_evidence_intake_record(
    *,
    organization_profile_id: str,
    evidence_label: str,
    evidence_type: str,
    application_workspace_id: str | None = None,
    pursuit_workspace_id: str | None = None,
    checklist_item_id: str | None = None,
    binder_item_id: str | None = None,
    forms_attachment_map_id: str | None = None,
    package_export_preview_id: str | None = None,
    source_context: str = "forms_attachments_map",
    provided_by: str | None = None,
    provided_at: str | None = None,
    storage_mode: str = "fixture_backed",
    storage_reference: str | None = None,
    hash_or_digest: str | None = None,
    file_name: str | None = None,
    mime_type: str | None = None,
    size_bytes: int | None = None,
    review_status: str = "needs_review",
    reviewer_role_required: str = "operator",
    human_review_required: bool = True,
) -> dict[str, Any]:
    mode = storage_mode if storage_mode in STORAGE_MODES else "not_supported"
    status = review_status if review_status in REVIEW_STATUSES else "needs_review"
    persistent = mode in _VALIDATED_PERSISTENT
    # Gate 10: upload persistence only for validated_persistent, local/dev scoped.
    # Customer/production persistence claims remain false always.
    upload_persistence_claimed = bool(persistent)
    customer_data_persistence_claimed = False
    production_storage_claimed = False
    package_unlock_claimed = False
    persistence_scope = "local_dev_only" if persistent else "not_claimed"
    if status in {"rejected", "blocked", "not_started", "needs_review"}:
        package_unlock_claimed = False
    if not persistent:
        upload_persistence_claimed = False

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "evidence_intake_id": make_evidence_intake_id(
                organization_profile_id, evidence_label
            ),
            "organization_profile_id": organization_profile_id,
            "application_workspace_id": application_workspace_id,
            "pursuit_workspace_id": pursuit_workspace_id,
            "checklist_item_id": checklist_item_id,
            "binder_item_id": binder_item_id,
            "forms_attachment_map_id": forms_attachment_map_id,
            "package_export_preview_id": package_export_preview_id,
            "evidence_type": evidence_type,
            "evidence_label": evidence_label,
            "source_context": source_context,
            "provided_by": provided_by,
            "provided_at": provided_at,
            "storage_mode": mode,
            "storage_reference": storage_reference,
            "hash_or_digest": hash_or_digest,
            "file_name": file_name,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "review_status": status,
            "reviewer_role_required": reviewer_role_required,
            "human_review_required": human_review_required,
            "package_unlock_claimed": package_unlock_claimed,
            "upload_persistence_claimed": upload_persistence_claimed,
            "persistence_scope": persistence_scope,
            "customer_data_persistence_claimed": customer_data_persistence_claimed,
            "production_storage_claimed": production_storage_claimed,
            "submission_ready_claimed": False,
            "final_export_claimed": False,
            "final_eligibility_claimed": False,
            "live_ingest_claimed": False,
        }
    )


def evidence_intake_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    mode = record.get("storage_mode")
    if mode not in STORAGE_MODES:
        fails.append("bad_storage_mode")
    if record.get("review_status") not in REVIEW_STATUSES:
        fails.append("bad_review_status")
    if (
        record.get("upload_persistence_claimed") is True
        and mode not in _VALIDATED_PERSISTENT
    ):
        fails.append("persistence_claimed_without_validated_storage")
    # Gate 10: customer/production persistence claims are never allowed
    if record.get("customer_data_persistence_claimed") is True:
        fails.append("customer_data_persistence_claimed")
    for key in (
        "production_storage_claimed",
        "package_unlock_claimed",
        "submission_ready_claimed",
        "final_export_claimed",
        "final_eligibility_claimed",
        "live_ingest_claimed",
    ):
        if record.get(key) is True:
            fails.append(key)
    if (
        record.get("upload_persistence_claimed") is True
        and record.get("persistence_scope") not in {None, "local_dev_only"}
        and mode in _VALIDATED_PERSISTENT
    ):
        fails.append("upload_persistence_scope_not_local_dev")
    if record.get("review_status") in {"rejected", "needs_review", "not_started"}:
        if record.get("package_unlock_claimed") is True:
            fails.append("unlock_with_unreviewed_or_rejected")
    return fails


def evidence_may_contribute_to_unlock(record: dict[str, Any]) -> bool:
    """Evidence exists is not enough — review + validated storage required."""
    if (
        record.get("human_review_required") is True
        and record.get("review_status") != "approved"
    ):
        return False
    if record.get("review_status") in {
        "rejected",
        "blocked",
        "not_started",
        "needs_review",
    }:
        return False
    if record.get("storage_mode") not in _VALIDATED_PERSISTENT:
        return False
    return True

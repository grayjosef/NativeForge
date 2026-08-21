"""Forms and attachments mapping contract (Campaign Block 16)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_forms_attachments_map_contract_v1"

MAPPING_STATUSES = frozenset(
    {
        "not_started",
        "mapped_from_source",
        "partial",
        "needs_confirmation",
        "not_in_source",
        "not_supported",
        "blocked",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_forms_attachment_map_id(application_workspace_id: str) -> str:
    raw = f"fa::{application_workspace_id}".encode()
    return f"fa_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_forms_attachments_map_contract(
    *,
    application_workspace_id: str,
    pursuit_workspace_id: str,
    opportunity_id: str,
    organization_profile_id: str,
    source_layer: str,
    source_reference: str | None = None,
    nofo_extraction_reference: str | None = None,
    checklist_reference: str | None = None,
    evidence_binder_reference: str | None = None,
    intake_reference: str | None = None,
    package_export_preview_reference: str | None = None,
    requirements_source: str = "nofo_pilot_and_checklist",
    form_items: list[dict[str, Any]] | None = None,
    attachment_items: list[dict[str, Any]] | None = None,
    mapping_status: str = "partial",
    human_review_required: bool = True,
) -> dict[str, Any]:
    status = (
        mapping_status if mapping_status in MAPPING_STATUSES else "needs_confirmation"
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "forms_attachment_map_id": make_forms_attachment_map_id(
                application_workspace_id
            ),
            "application_workspace_id": application_workspace_id,
            "pursuit_workspace_id": pursuit_workspace_id,
            "opportunity_id": opportunity_id,
            "organization_profile_id": organization_profile_id,
            "source_layer": source_layer,
            "source_reference": source_reference,
            "nofo_extraction_reference": nofo_extraction_reference,
            "checklist_reference": checklist_reference,
            "evidence_binder_reference": evidence_binder_reference,
            "intake_reference": intake_reference,
            "package_export_preview_reference": package_export_preview_reference,
            "requirements_source": requirements_source,
            "form_items": list(form_items or []),
            "attachment_items": list(attachment_items or []),
            "mapping_status": status,
            "human_review_required": human_review_required,
            "binary_upload_supported": False,
            "attachment_persistence_claimed": False,
            "form_completion_claimed": False,
            "submission_ready_claimed": False,
            "final_eligibility_claimed": False,
            "live_ingest_claimed": False,
        }
    )


def forms_attachments_map_invariant_failures(packet: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "binary_upload_supported",
        "attachment_persistence_claimed",
        "form_completion_claimed",
        "submission_ready_claimed",
        "final_eligibility_claimed",
        "live_ingest_claimed",
    ):
        if packet.get(key) is True:
            fails.append(key)
    if packet.get("mapping_status") not in MAPPING_STATUSES:
        fails.append("bad_mapping_status")
    for item in list(packet.get("form_items") or []) + list(
        packet.get("attachment_items") or []
    ):
        if item.get("completed") is True:
            fails.append(f"item_completed:{item.get('item_id')}")
        if item.get("uploaded") is True:
            fails.append(f"item_uploaded:{item.get('item_id')}")
        if item.get("persistence_claimed") is True:
            fails.append(f"item_persistence:{item.get('item_id')}")
    return fails

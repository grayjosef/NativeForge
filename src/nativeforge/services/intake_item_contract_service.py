"""Intake item contract (Campaign Block 05).

Represents planned evidence/confirmation/approval requests for checklist gaps.
Does not claim binary upload persistence or close gaps without evidence/approval.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_intake_item_contract_v1"

INTAKE_TYPES: frozenset[str] = frozenset(
    {
        "document_upload_needed",
        "form_confirmation_needed",
        "org_fact_confirmation_needed",
        "eligibility_confirmation_needed",
        "budget_confirmation_needed",
        "match_confirmation_needed",
        "tribal_resolution_needed",
        "partner_confirmation_needed",
        "fiscal_sponsor_confirmation_needed",
        "human_approval_needed",
        "not_supported",
    }
)

INTAKE_STATUSES: frozenset[str] = frozenset(
    {
        "planned",
        "requested",
        "awaiting_evidence",
        "awaiting_approval",
        "needs_more_information",
        "satisfied",
        "blocked",
        "not_supported",
    }
)

APPROVAL_STATUSES: frozenset[str] = frozenset(
    {
        "not_started",
        "needs_reviewer",
        "pending_review",
        "approved",
        "rejected",
        "needs_more_information",
        "blocked",
        "not_required",
    }
)

ACCEPTED_EVIDENCE_TYPES: frozenset[str] = frozenset(
    {
        "official_document",
        "form_confirmation",
        "org_fact_confirmation",
        "eligibility_language_confirmation",
        "budget_confirmation",
        "match_confirmation",
        "tribal_resolution",
        "partner_letter",
        "fiscal_sponsor_agreement",
        "human_approval_record",
        "not_applicable",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_intake_item_id(
    application_workspace_id: str, checklist_item_id: str, intake_type: str
) -> str:
    raw = f"{application_workspace_id}::{checklist_item_id}::{intake_type}".encode()
    return f"in_{hashlib.sha256(raw).hexdigest()[:16]}"


def make_intake_item(
    *,
    application_workspace_id: str,
    pursuit_workspace_id: str,
    checklist_item_id: str,
    binder_item_id: str | None,
    intake_type: str,
    requested_from: str,
    item_label: str,
    item_description: str,
    accepted_evidence_types: list[str] | None = None,
    current_status: str = "planned",
    evidence_reference: str | None = None,
    missing_reason: str = "",
    due_before_status_change: str = "package_readiness",
    customer_action_required: bool = False,
    operator_action_required: bool = True,
    human_review_required: bool = True,
    approval_required: bool = True,
    approval_status: str = "not_started",
    final_package_unlocks: bool = False,
    unsupported_claim_guard: bool = False,
    source_checklist_section: str | None = None,
    why_it_matters: str = "",
    what_remains_blocked: str = "",
) -> dict[str, Any]:
    itype = intake_type if intake_type in INTAKE_TYPES else "not_supported"
    status = current_status if current_status in INTAKE_STATUSES else "planned"
    astatus = approval_status if approval_status in APPROVAL_STATUSES else "not_started"
    accepted = [
        t
        for t in (accepted_evidence_types or ["official_document"])
        if t in ACCEPTED_EVIDENCE_TYPES
    ] or ["not_applicable"]

    if unsupported_claim_guard or itype == "not_supported":
        status = "not_supported"
        astatus = "blocked"
        final_package_unlocks = False

    # Never start as satisfied without evidence + approval when required
    if status == "satisfied":
        if not evidence_reference:
            status = "awaiting_evidence"
        elif approval_required and astatus != "approved":
            status = "awaiting_approval"
            astatus = astatus if astatus != "not_started" else "needs_reviewer"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "intake_item_id": make_intake_item_id(
                application_workspace_id, checklist_item_id, itype
            ),
            "application_workspace_id": application_workspace_id,
            "pursuit_workspace_id": pursuit_workspace_id,
            "checklist_item_id": checklist_item_id,
            "binder_item_id": binder_item_id,
            "intake_type": itype,
            "requested_from": requested_from,
            "item_label": item_label,
            "item_description": item_description,
            "accepted_evidence_types": accepted,
            "current_status": status,
            "evidence_reference": evidence_reference,
            "missing_reason": missing_reason,
            "due_before_status_change": due_before_status_change,
            "customer_action_required": customer_action_required,
            "operator_action_required": operator_action_required,
            "human_review_required": human_review_required,
            "approval_required": approval_required,
            "approval_status": astatus,
            "final_package_unlocks": final_package_unlocks,
            "unsupported_claim_guard": unsupported_claim_guard
            or itype == "not_supported",
            "source_checklist_section": source_checklist_section,
            "why_it_matters": why_it_matters,
            "what_remains_blocked": what_remains_blocked,
            "gap_closed": False,
            "binary_upload_persistence_supported": False,
            "binary_upload_persistence_claimed": False,
            "approval_persistence_supported": False,
            "approval_persistence_claimed": False,
            "proposal_drafting_claimed": False,
            "fabricated": False,
        }
    )


def attempt_close_intake_gap(
    item: dict[str, Any],
    *,
    evidence_present: bool,
    approval_granted: bool = False,
) -> dict[str, Any]:
    """Refuse gap closure without evidence and required approval."""
    out = dict(item)
    if out.get("unsupported_claim_guard") or out.get("intake_type") == "not_supported":
        out["current_status"] = "not_supported"
        out["gap_closed"] = False
        out["closure_refused_reason"] = "unsupported_claim_guard"
        return _json_safe(out)
    if not evidence_present:
        out["current_status"] = "awaiting_evidence"
        out["gap_closed"] = False
        out["closure_refused_reason"] = "missing_evidence"
        return _json_safe(out)
    if out.get("approval_required") and not approval_granted:
        out["current_status"] = "awaiting_approval"
        out["approval_status"] = "needs_reviewer"
        out["gap_closed"] = False
        out["closure_refused_reason"] = "approval_required"
        return _json_safe(out)
    out["current_status"] = "satisfied"
    out["approval_status"] = (
        "approved" if out.get("approval_required") else "not_required"
    )
    out["gap_closed"] = True
    out["closure_refused_reason"] = None
    # Still no persistence claims
    out["binary_upload_persistence_claimed"] = False
    out["approval_persistence_claimed"] = False
    return _json_safe(out)


def intake_item_invariant_failures(item: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if item.get("intake_type") not in INTAKE_TYPES:
        fails.append(f"bad_type:{item.get('intake_item_id')}")
    if item.get("current_status") not in INTAKE_STATUSES:
        fails.append(f"bad_status:{item.get('intake_item_id')}")
    if item.get("approval_status") not in APPROVAL_STATUSES:
        fails.append(f"bad_approval:{item.get('intake_item_id')}")
    if item.get("binary_upload_persistence_claimed") is True:
        fails.append(f"upload_claimed:{item.get('intake_item_id')}")
    if item.get("approval_persistence_claimed") is True:
        fails.append(f"approval_persist_claimed:{item.get('intake_item_id')}")
    if item.get("proposal_drafting_claimed") is True:
        fails.append(f"proposal_claimed:{item.get('intake_item_id')}")
    if item.get("fabricated") is True:
        fails.append(f"fabricated:{item.get('intake_item_id')}")
    if item.get("gap_closed") is True:
        if (
            not item.get("evidence_reference")
            and item.get("closure_refused_reason") is None
        ):
            # closed via attempt_close may not set evidence_reference; require status
            if item.get("current_status") != "satisfied":
                fails.append(f"closed_not_satisfied:{item.get('intake_item_id')}")
        if item.get("approval_required") and item.get("approval_status") != "approved":
            fails.append(f"closed_without_approval:{item.get('intake_item_id')}")
        if item.get("unsupported_claim_guard"):
            fails.append(f"closed_unsupported:{item.get('intake_item_id')}")
    if item.get("final_package_unlocks") is True and item.get("gap_closed") is not True:
        fails.append(f"unlock_without_close:{item.get('intake_item_id')}")
    return fails

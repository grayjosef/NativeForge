"""Application checklist execution contract (Campaign Block 04).

Turns pursuit/evidence binder into executable checklist items.
Does not mark items complete without evidence or explicit human review.
Does not fabricate proposal narrative or allow submission.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_application_checklist_execution_contract_v1"

ITEM_STATUSES: frozenset[str] = frozenset(
    {
        "pending",
        "in_progress",
        "needs_evidence",
        "needs_human_review",
        "needs_confirmation",
        "complete",
        "not_supported",
        "blocked",
    }
)

READINESS_IMPACTS: frozenset[str] = frozenset(
    {
        "blocks_submission",
        "blocks_completeness",
        "needs_review",
        "informational",
        "unsupported_defer",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_application_workspace_id(pursuit_workspace_id: str) -> str:
    raw = f"app::{pursuit_workspace_id}".encode()
    return f"aw_{hashlib.sha256(raw).hexdigest()[:16]}"


def make_checklist_item(
    *,
    item_id: str,
    section_id: str,
    label: str,
    item_source: str,
    item_status: str = "pending",
    evidence_reference: str | None = None,
    missing_information_reference: str | None = None,
    what_nativeforge_knows: str = "",
    what_is_missing: list[str] | None = None,
    next_action: str = "",
    required_human_review: bool = True,
    customer_action_required: bool = False,
    operator_action_required: bool = True,
    readiness_impact: str = "blocks_completeness",
    unsupported_claim_guard: bool = False,
) -> dict[str, Any]:
    status = item_status if item_status in ITEM_STATUSES else "pending"
    impact = (
        readiness_impact
        if readiness_impact in READINESS_IMPACTS
        else "blocks_completeness"
    )
    missing = list(what_is_missing or [])
    # Completion without evidence or human review is forbidden at construction.
    if status == "complete":
        if unsupported_claim_guard:
            status = "not_supported"
        elif missing or not evidence_reference:
            status = "needs_evidence"
        elif required_human_review:
            status = "needs_human_review"
    return _json_safe(
        {
            "item_id": item_id,
            "section_id": section_id,
            "label": label,
            "item_source": item_source,
            "item_status": status,
            "evidence_reference": evidence_reference,
            "missing_information_reference": missing_information_reference,
            "what_nativeforge_knows": what_nativeforge_knows,
            "what_is_missing": missing,
            "next_action": next_action,
            "required_human_review": required_human_review,
            "customer_action_required": customer_action_required,
            "operator_action_required": operator_action_required,
            "readiness_impact": impact,
            "unsupported_claim_guard": unsupported_claim_guard,
            "fabricated": False,
            "proposal_drafting_claimed": False,
        }
    )


def mark_checklist_item_complete(
    item: dict[str, Any],
    *,
    evidence_present: bool,
    human_review_acknowledged: bool = False,
) -> dict[str, Any]:
    """Attempt completion; refuses without evidence / required human review."""
    out = dict(item)
    if out.get("unsupported_claim_guard"):
        out["item_status"] = "not_supported"
        out["completion_refused_reason"] = "unsupported_claim_guard"
        return _json_safe(out)
    if not evidence_present:
        out["item_status"] = "needs_evidence"
        out["completion_refused_reason"] = "missing_evidence"
        return _json_safe(out)
    if out.get("required_human_review") and not human_review_acknowledged:
        out["item_status"] = "needs_human_review"
        out["completion_refused_reason"] = "human_review_required"
        return _json_safe(out)
    if out.get("what_is_missing"):
        out["item_status"] = "needs_evidence"
        out["completion_refused_reason"] = "missing_fields_remain"
        return _json_safe(out)
    out["item_status"] = "complete"
    out["completion_refused_reason"] = None
    out["evidence_present_at_completion"] = True
    out["human_review_acknowledged"] = human_review_acknowledged
    return _json_safe(out)


def build_application_checklist_execution_contract(
    *,
    pursuit_workspace_id: str,
    opportunity_id: str,
    organization_profile_id: str,
    checklist_sections: list[dict[str, Any]] | None = None,
    checklist_items: list[dict[str, Any]] | None = None,
    evidence_binder_reference: str | None = None,
    eligibility_evidence_reference: str | None = None,
    nofo_intelligence_reference: str | None = None,
) -> dict[str, Any]:
    sections = list(checklist_sections or [])
    items = list(checklist_items or [])
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "application_workspace_id": make_application_workspace_id(
                pursuit_workspace_id
            ),
            "pursuit_workspace_id": pursuit_workspace_id,
            "opportunity_id": opportunity_id,
            "organization_profile_id": organization_profile_id,
            "checklist_sections": sections,
            "checklist_items": items,
            "item_count": len(items),
            "section_count": len(sections),
            "evidence_binder_reference": evidence_binder_reference,
            "eligibility_evidence_reference": eligibility_evidence_reference,
            "nofo_intelligence_reference": nofo_intelligence_reference,
            "required_human_review": True,
            "customer_action_required": any(
                i.get("customer_action_required") for i in items
            ),
            "operator_action_required": any(
                i.get("operator_action_required") for i in items
            ),
            "unsupported_claim_guard": True,
            "submission_allowed": False,
            "submission_ready_claimed": False,
            "proposal_drafting_claimed": False,
            "nofo_pdf_extraction_claimed": False,
            "live_ingest_claimed": False,
            "scoring_math_changed": False,
            "application_complete_claimed": False,
            "why_submission_not_allowed": (
                "Package checklist incomplete; evidence gaps remain; "
                "human review required; proposal drafting not supported; "
                "auto-submit disabled."
            ),
        }
    )


def checklist_execution_invariant_failures(contract: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if contract.get("submission_allowed") is not False:
        fails.append("submission_allowed")
    if contract.get("submission_ready_claimed") is True:
        fails.append("submission_ready_claimed")
    if contract.get("proposal_drafting_claimed") is True:
        fails.append("proposal_drafting_claimed")
    if contract.get("nofo_pdf_extraction_claimed") is True:
        fails.append("nofo_pdf_extraction_claimed")
    if contract.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    if contract.get("scoring_math_changed") is True:
        fails.append("scoring_math_changed")
    if contract.get("application_complete_claimed") is True:
        fails.append("application_complete_claimed")
    if contract.get("unsupported_claim_guard") is not True:
        fails.append("unsupported_claim_guard_missing")
    if not contract.get("application_workspace_id"):
        fails.append("application_workspace_id")
    if not contract.get("pursuit_workspace_id"):
        fails.append("pursuit_workspace_id")
    for item in contract.get("checklist_items") or []:
        fails.extend(checklist_item_invariant_failures(item))
    return fails


def checklist_item_invariant_failures(item: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    status = item.get("item_status")
    if status not in ITEM_STATUSES:
        fails.append(f"bad_status:{item.get('item_id')}")
    if item.get("fabricated") is True:
        fails.append(f"fabricated:{item.get('item_id')}")
    if item.get("proposal_drafting_claimed") is True:
        fails.append(f"proposal_claimed:{item.get('item_id')}")
    if status == "complete":
        if item.get("unsupported_claim_guard"):
            fails.append(f"complete_unsupported:{item.get('item_id')}")
        if item.get("what_is_missing"):
            fails.append(f"complete_with_missing:{item.get('item_id')}")
        if not item.get("evidence_reference") and not item.get(
            "evidence_present_at_completion"
        ):
            fails.append(f"complete_without_evidence:{item.get('item_id')}")
        if item.get("required_human_review") and not item.get(
            "human_review_acknowledged"
        ):
            fails.append(f"complete_without_human_review:{item.get('item_id')}")
    if item.get("unsupported_claim_guard") and status == "complete":
        fails.append(f"unsupported_complete:{item.get('item_id')}")
    return fails

"""Human approval workflow model for package gates (Campaign Block 05).

Represents required approvals honestly. Does not claim durable approval persistence
or real auth/role enforcement unless already present (it is not).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.intake_item_contract_service import APPROVAL_STATUSES

SCHEMA_VERSION = "nf_human_approval_workflow_v1"

APPROVAL_TYPES: frozenset[str] = frozenset(
    {
        "package_completeness",
        "eligibility_language",
        "organization_fact",
        "document_evidence",
        "form_confirmation",
        "budget_match",
        "tribal_resolution",
        "partner_fiscal",
        "unsupported_deferral",
    }
)

REVIEWER_ROLES: frozenset[str] = frozenset(
    {
        "customer_grant_lead",
        "tribal_administrator",
        "operator_reviewer",
        "compliance_reviewer",
        "unassigned",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_approval_id(intake_item_id: str, approval_type: str) -> str:
    raw = f"{intake_item_id}::{approval_type}".encode()
    return f"ap_{hashlib.sha256(raw).hexdigest()[:16]}"


def _approval_type_for_intake(intake_type: str) -> str:
    return {
        "document_upload_needed": "document_evidence",
        "form_confirmation_needed": "form_confirmation",
        "org_fact_confirmation_needed": "organization_fact",
        "eligibility_confirmation_needed": "eligibility_language",
        "budget_confirmation_needed": "budget_match",
        "match_confirmation_needed": "budget_match",
        "tribal_resolution_needed": "tribal_resolution",
        "partner_confirmation_needed": "partner_fiscal",
        "fiscal_sponsor_confirmation_needed": "partner_fiscal",
        "human_approval_needed": "package_completeness",
        "not_supported": "unsupported_deferral",
    }.get(intake_type, "package_completeness")


def _role_for_intake(intake_type: str, requested_from: str) -> str:
    if intake_type in {
        "tribal_resolution_needed",
        "org_fact_confirmation_needed",
    }:
        return "tribal_administrator"
    if intake_type in {
        "budget_confirmation_needed",
        "match_confirmation_needed",
        "partner_confirmation_needed",
        "fiscal_sponsor_confirmation_needed",
        "document_upload_needed",
    }:
        return "customer_grant_lead"
    if intake_type == "eligibility_confirmation_needed":
        return "compliance_reviewer"
    if requested_from == "customer":
        return "customer_grant_lead"
    return "operator_reviewer"


def make_approval_record(
    *,
    intake_item: dict[str, Any],
    application_workspace_id: str,
    pursuit_workspace_id: str,
) -> dict[str, Any]:
    intake_type = str(intake_item.get("intake_type") or "not_supported")
    approval_type = _approval_type_for_intake(intake_type)
    role = _role_for_intake(
        intake_type, str(intake_item.get("requested_from") or "operator")
    )
    unsupported = bool(intake_item.get("unsupported_claim_guard"))
    status = "blocked" if unsupported else "needs_reviewer"
    cannot_unlock = (
        "Unsupported capability cannot unlock package readiness."
        if unsupported
        else (
            "Cannot unlock package readiness until evidence is reviewed and "
            "human approval is recorded. Approval persistence is not implemented "
            "in this layer — status is planned/demo workflow only."
        )
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "approval_id": make_approval_id(
                str(intake_item.get("intake_item_id")), approval_type
            ),
            "approval_type": approval_type
            if approval_type in APPROVAL_TYPES
            else "package_completeness",
            "linked_application_workspace_id": application_workspace_id,
            "linked_pursuit_workspace_id": pursuit_workspace_id,
            "linked_intake_item_id": intake_item.get("intake_item_id"),
            "linked_checklist_item_id": intake_item.get("checklist_item_id"),
            "linked_binder_item_id": intake_item.get("binder_item_id"),
            "required_reviewer_role": role,
            "role_enforcement_implemented": False,
            "approval_status": status if status in APPROVAL_STATUSES else "blocked",
            "approved_by": None,
            "approved_at": None,
            "evidence_reviewed": False,
            "comments_required": True,
            "unlocks_status": False,
            "cannot_unlock_reason": cannot_unlock,
            "approval_persistence_supported": False,
            "approval_persistence_claimed": False,
            "submission_ready_unlocked": False,
            "proposal_drafting_claimed": False,
        }
    )


def build_human_approval_workflow(
    *,
    intake_plan: dict[str, Any],
    application_workspace_id: str,
    pursuit_workspace_id: str,
) -> dict[str, Any]:
    approvals: list[dict[str, Any]] = []
    for item in intake_plan.get("intake_items") or []:
        if (
            not item.get("approval_required")
            and item.get("intake_type") != "not_supported"
        ):
            continue
        approvals.append(
            make_approval_record(
                intake_item=item,
                application_workspace_id=application_workspace_id,
                pursuit_workspace_id=pursuit_workspace_id,
            )
        )

    open_count = sum(
        1
        for a in approvals
        if a.get("approval_status") not in {"approved", "not_required"}
    )
    any_unlock = any(a.get("unlocks_status") for a in approvals)
    any_submission = any(a.get("submission_ready_unlocked") for a in approvals)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "application_workspace_id": application_workspace_id,
            "pursuit_workspace_id": pursuit_workspace_id,
            "approval_count": len(approvals),
            "open_approval_count": open_count,
            "approvals": approvals,
            "package_readiness_unlocked": False,
            "submission_ready_claimed": False,
            "approval_persistence_supported": False,
            "approval_persistence_claimed": False,
            "role_enforcement_implemented": False,
            "any_unlocks_status": any_unlock,
            "any_submission_ready_unlocked": any_submission,
            "package_blocked_reasons": [
                "Open human approvals remain",
                "Evidence not yet reviewed for intake gaps",
                "Approval persistence not implemented — no durable unlock",
                "Submission remains disallowed",
            ],
        }
    )


def approval_workflow_invariant_failures(workflow: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if workflow.get("package_readiness_unlocked") is True:
        fails.append("package_readiness_unlocked")
    if workflow.get("submission_ready_claimed") is True:
        fails.append("submission_ready_claimed")
    if workflow.get("approval_persistence_claimed") is True:
        fails.append("approval_persistence_claimed")
    if workflow.get("approval_persistence_supported") is True:
        fails.append("approval_persistence_supported_false_positive")
    if workflow.get("any_unlocks_status") is True:
        fails.append("any_unlocks_status")
    if workflow.get("any_submission_ready_unlocked") is True:
        fails.append("any_submission_ready_unlocked")
    for a in workflow.get("approvals") or []:
        if a.get("approval_status") not in APPROVAL_STATUSES:
            fails.append(f"bad_status:{a.get('approval_id')}")
        if a.get("approval_type") not in APPROVAL_TYPES:
            fails.append(f"bad_type:{a.get('approval_id')}")
        if a.get("required_reviewer_role") not in REVIEWER_ROLES:
            fails.append(f"bad_role:{a.get('approval_id')}")
        if a.get("unlocks_status") is True:
            fails.append(f"unlock:{a.get('approval_id')}")
        if a.get("submission_ready_unlocked") is True:
            fails.append(f"submit_unlock:{a.get('approval_id')}")
        if a.get("approval_persistence_claimed") is True:
            fails.append(f"persist_claimed:{a.get('approval_id')}")
        if a.get("approved_by") is not None or a.get("approved_at") is not None:
            # Demo workflow must not fabricate completed approvals
            fails.append(f"fabricated_approval:{a.get('approval_id')}")
        if a.get("role_enforcement_implemented") is True:
            fails.append(f"role_enforced:{a.get('approval_id')}")
    return fails

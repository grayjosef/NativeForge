"""Pursuit workspace contract (Campaign Block 03).

Connects opportunity + org + eligibility + NOFO + plan into a review-gated workspace.
Does not claim submission-ready or fabricate proposal narrative.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_pursuit_workspace_contract_v1"

PURSUIT_STATUSES: frozenset[str] = frozenset(
    {
        "draft",
        "under_review",
        "needs_information",
        "deferred",
        "blocked",
        "closed",
    }
)

READINESS_STATUSES: frozenset[str] = frozenset(
    {
        "ready_for_review",
        "needs_information",
        "needs_source_confirmation",
        "needs_org_confirmation",
        "blocked_missing_eligibility_evidence",
        "blocked_unsupported_requirement",
        "not_submission_ready",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_pursuit_workspace_id(opportunity_id: str, profile_id: str) -> str:
    raw = f"{opportunity_id}::{profile_id}".encode()
    return f"pw_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_pursuit_workspace_contract(
    *,
    opportunity_id: str,
    organization_profile_id: str,
    opportunity_source_layer: str,
    eligibility_evidence_reference: str | None = None,
    nofo_intelligence_reference: str | None = None,
    application_plan_reference: str | None = None,
    evidence_binder_reference: str | None = None,
    pursuit_status: str = "under_review",
    readiness_status: str = "not_submission_ready",
    missing_information_summary: list[str] | None = None,
    operator_next_actions: list[str] | None = None,
    customer_next_actions: list[str] | None = None,
    human_review_required: bool = True,
    why_worth_review: str | None = None,
) -> dict[str, Any]:
    missing = list(missing_information_summary or [])
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "pursuit_workspace_id": make_pursuit_workspace_id(
                opportunity_id, organization_profile_id
            ),
            "opportunity_id": opportunity_id,
            "organization_profile_id": organization_profile_id,
            "opportunity_source_layer": opportunity_source_layer,
            "eligibility_evidence_reference": eligibility_evidence_reference
            or f"eligibility:{opportunity_id}:{organization_profile_id}",
            "nofo_intelligence_reference": nofo_intelligence_reference
            or f"nofo:{opportunity_id}",
            "application_plan_reference": application_plan_reference
            or f"plan:{opportunity_id}",
            "evidence_binder_reference": evidence_binder_reference
            or f"binder:{opportunity_id}:{organization_profile_id}",
            "pursuit_status": pursuit_status,
            "readiness_status": readiness_status,
            "missing_information_summary": missing,
            "human_review_required": human_review_required,
            "operator_next_actions": list(
                operator_next_actions
                or ["Human review required before pursuit decision"]
            ),
            "customer_next_actions": list(
                customer_next_actions
                or ["Provide missing organization facts only when verified"]
            ),
            "why_worth_review": why_worth_review
            or "Opportunity is curated-current and worth structured human review",
            "final_submission_allowed": False,
            "submission_ready_claimed": False,
            "proposal_drafting_claimed": False,
            "nofo_pdf_extraction_claimed": False,
            "live_ingest_claimed": False,
            "scoring_math_changed": False,
        }
    )


def pursuit_workspace_invariant_failures(ws: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    required = [
        "pursuit_workspace_id",
        "opportunity_id",
        "organization_profile_id",
        "opportunity_source_layer",
        "eligibility_evidence_reference",
        "nofo_intelligence_reference",
        "application_plan_reference",
        "evidence_binder_reference",
        "pursuit_status",
        "readiness_status",
        "missing_information_summary",
        "human_review_required",
        "operator_next_actions",
        "customer_next_actions",
    ]
    for key in required:
        if key not in ws:
            fails.append(f"missing_{key}")
    if ws.get("final_submission_allowed") is True:
        fails.append("final_submission_allowed")
    if ws.get("submission_ready_claimed") is True:
        fails.append("submission_ready_claimed")
    if ws.get("proposal_drafting_claimed") is True:
        fails.append("proposal_drafting_claimed")
    if ws.get("nofo_pdf_extraction_claimed") is True:
        fails.append("nofo_pdf_claimed")
    if ws.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    if ws.get("scoring_math_changed") is True:
        fails.append("scoring_math_changed")
    if ws.get("human_review_required") is not True:
        fails.append("human_review_required")
    if ws.get("pursuit_status") not in PURSUIT_STATUSES:
        fails.append(f"bad_pursuit_status:{ws.get('pursuit_status')}")
    if ws.get("readiness_status") not in READINESS_STATUSES:
        fails.append(f"bad_readiness_status:{ws.get('readiness_status')}")
    # Cannot claim submission-ready without complete package + human review
    if ws.get("readiness_status") != "not_submission_ready":
        # Any non-blocked readiness still cannot flip submission flags
        if ws.get("final_submission_allowed") or ws.get("submission_ready_claimed"):
            fails.append("non_submission_status_with_submit_claim")
    if "missing_information_summary" in ws and not isinstance(
        ws.get("missing_information_summary"), list
    ):
        fails.append("missing_information_not_list")
    # If missing info exists, readiness must reflect not submission ready
    if ws.get("missing_information_summary") and ws.get("readiness_status") not in {
        "needs_information",
        "needs_source_confirmation",
        "needs_org_confirmation",
        "blocked_missing_eligibility_evidence",
        "blocked_unsupported_requirement",
        "not_submission_ready",
        "ready_for_review",
    }:
        fails.append("missing_info_bad_readiness")
    if ws.get("missing_information_summary") and ws.get("submission_ready_claimed"):
        fails.append("missing_info_but_submission_ready")
    if not ws.get("human_review_required") and ws.get("submission_ready_claimed"):
        fails.append("submission_without_human_review")
    return fails

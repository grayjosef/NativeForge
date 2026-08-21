"""Deterministic AI governance contract (Campaign Block 13)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_ai_governance_contract_v1"

CHECK_SCOPES = frozenset(
    {
        "organization_profile_alignment",
        "tribal_recognition_alignment",
        "eligibility_claim_alignment",
        "nofo_requirement_alignment",
        "budget_match_alignment",
        "citation_presence",
        "prohibited_fact_scan",
        "unsupported_claim_scan",
        "personalization_attribution",
        "human_review_gate",
        "submission_claim_guard",
    }
)

CHECK_STATUSES = frozenset(
    {
        "pass",
        "warning",
        "blocked",
        "needs_evidence",
        "needs_human_review",
        "not_supported",
    }
)

HARD_GATE_STATUSES = frozenset(
    {
        "open",
        "blocked",
        "requires_review",
        "passed_for_review_only",
        "not_submission_ready",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_ai_governance_check_id(
    draft_workspace_id: str, section_id: str, check_scope: str
) -> str:
    raw = f"ag::{draft_workspace_id}::{section_id}::{check_scope}".encode()
    return f"ag_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_ai_governance_check(
    *,
    draft_workspace_id: str,
    controlled_draft_id: str | None,
    application_workspace_id: str,
    pursuit_workspace_id: str,
    organization_profile_id: str,
    organization_evidence_profile_id: str | None,
    opportunity_id: str,
    source_layer: str,
    section_id: str,
    check_scope: str,
    check_status: str,
    hard_gate_status: str,
    issue_summary: str | None = None,
    required_evidence: list[str] | None = None,
    recommended_next_action: str | None = None,
    human_review_required: bool = True,
) -> dict[str, Any]:
    scope = check_scope if check_scope in CHECK_SCOPES else "unsupported_claim_scan"
    status = check_status if check_status in CHECK_STATUSES else "needs_human_review"
    hard = (
        hard_gate_status
        if hard_gate_status in HARD_GATE_STATUSES
        else "not_submission_ready"
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "ai_governance_check_id": make_ai_governance_check_id(
                draft_workspace_id, section_id, scope
            ),
            "draft_workspace_id": draft_workspace_id,
            "controlled_draft_id": controlled_draft_id,
            "application_workspace_id": application_workspace_id,
            "pursuit_workspace_id": pursuit_workspace_id,
            "organization_profile_id": organization_profile_id,
            "organization_evidence_profile_id": organization_evidence_profile_id,
            "opportunity_id": opportunity_id,
            "source_layer": source_layer,
            "section_id": section_id,
            "check_scope": scope,
            "check_status": status,
            "hard_gate_status": hard,
            "issue_summary": issue_summary,
            "required_evidence": list(required_evidence or []),
            "recommended_next_action": recommended_next_action,
            "human_review_required": human_review_required,
            "qa_passed": False,
            "submission_ready_claimed": False,
            "final_application_claimed": False,
            "final_eligibility_claimed": False,
            "live_ingest_claimed": False,
        }
    )


def ai_governance_check_invariant_failures(check: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "qa_passed",
        "submission_ready_claimed",
        "final_application_claimed",
        "final_eligibility_claimed",
        "live_ingest_claimed",
    ):
        if check.get(key) is True:
            fails.append(key)
    if check.get("check_scope") not in CHECK_SCOPES:
        fails.append("bad_scope")
    if check.get("check_status") not in CHECK_STATUSES:
        fails.append("bad_status")
    if check.get("hard_gate_status") not in HARD_GATE_STATUSES:
        fails.append("bad_hard_gate")
    # Missing evidence cannot pass
    if check.get("check_status") == "needs_evidence" and check.get("qa_passed") is True:
        fails.append("qa_passed_with_missing_evidence")
    return fails

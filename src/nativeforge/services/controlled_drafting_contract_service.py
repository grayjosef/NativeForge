"""Evidence-cited controlled drafting contract (Campaign Block 12)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_controlled_drafting_contract_v1"

DRAFTING_MODES = frozenset(
    {
        "evidence_only",
        "placeholder_only",
        "question_only",
        "not_supported",
        "blocked_missing_evidence",
    }
)

GENERATION_STATUSES = frozenset(
    {
        "not_started",
        "generated_from_evidence",
        "placeholder_generated",
        "questions_generated",
        "blocked",
        "needs_human_review",
        "not_supported",
    }
)

PROHIBITED_GENERATION = frozenset(
    {
        "budget_amounts",
        "match_amounts",
        "tribal_history",
        "community_statistics",
        "partner_commitments",
        "prior_awards",
        "outcomes",
        "staffing_claims",
        "certifications",
        "resolutions",
        "final_eligibility",
        "submission_ready",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_controlled_draft_id(draft_workspace_id: str, section_id: str) -> str:
    raw = f"cd::{draft_workspace_id}::{section_id}".encode()
    return f"cd_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_controlled_draft_record(
    *,
    draft_workspace_id: str,
    application_workspace_id: str,
    pursuit_workspace_id: str,
    opportunity_id: str,
    organization_profile_id: str,
    section_id: str,
    drafting_mode: str,
    generation_status: str,
    evidence_inputs: list[dict[str, Any]] | None = None,
    missing_inputs: list[str] | None = None,
    citation_requirements: list[str] | None = None,
    generated_text: str | None = None,
    placeholders: list[str] | None = None,
    question_prompts: list[str] | None = None,
    unsupported_claim_guard: bool = True,
    human_review_required: bool = True,
) -> dict[str, Any]:
    mode = drafting_mode if drafting_mode in DRAFTING_MODES else "not_supported"
    status = (
        generation_status
        if generation_status in GENERATION_STATUSES
        else "needs_human_review"
    )
    evidence = list(evidence_inputs or [])
    # Evidence-only generation requires citations
    if mode == "evidence_only" and generated_text and not evidence:
        mode = "blocked_missing_evidence"
        status = "blocked"
        generated_text = None
        placeholders = [
            "[MISSING EVIDENCE: cannot generate without citations]",
        ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "controlled_draft_id": make_controlled_draft_id(
                draft_workspace_id, section_id
            ),
            "draft_workspace_id": draft_workspace_id,
            "application_workspace_id": application_workspace_id,
            "pursuit_workspace_id": pursuit_workspace_id,
            "opportunity_id": opportunity_id,
            "organization_profile_id": organization_profile_id,
            "section_id": section_id,
            "drafting_mode": mode,
            "evidence_inputs": evidence,
            "missing_inputs": list(missing_inputs or []),
            "citation_requirements": list(citation_requirements or []),
            "generation_status": status,
            "generated_text": generated_text,
            "placeholders": list(placeholders or []),
            "question_prompts": list(question_prompts or []),
            "unsupported_claim_guard": unsupported_claim_guard,
            "human_review_required": human_review_required,
            "final_text_claimed": False,
            "submission_ready_claimed": False,
            "complete_proposal_claimed": False,
            "proposal_drafting_claimed": False,
            "live_ingest_claimed": False,
            "prohibited_generation_blocked": sorted(PROHIBITED_GENERATION),
            "generated_draft_warning": (
                "DRAFT ONLY — evidence-cited controlled drafting v0; "
                "human review required; not final; not submission-ready"
            ),
        }
    )


def controlled_draft_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "final_text_claimed",
        "submission_ready_claimed",
        "complete_proposal_claimed",
        "proposal_drafting_claimed",
        "live_ingest_claimed",
    ):
        if record.get(key) is True:
            fails.append(key)
    if record.get("drafting_mode") == "evidence_only" and record.get("generated_text"):
        if not record.get("evidence_inputs"):
            fails.append("generated_without_citations")
        if not record.get("human_review_required"):
            fails.append("generated_without_human_review")
    # Guard fabricated money
    text = record.get("generated_text") or ""
    if any(x in text.lower() for x in ("$", "usd", "dollars")):
        fails.append("budget_fabrication_in_generated_text")
    return fails
